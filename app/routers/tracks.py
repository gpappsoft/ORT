# Copyright (c) 2025 Marco Moenig (info@moenig.it)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT


import zipfile

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Depends, Security, Query
from fastapi.responses import StreamingResponse
from typing import Annotated
from sqlalchemy.future import select
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime
from io import BytesIO
from loguru import logger

from app.models import User,Track,TrackPoints,TrackSummary,TrackLinestring,TrackDetails,TrackDetailsWithData,TrackBase
from app.lib.auth import get_current_active_user
from app.db import get_session
from app.lib.tracks import get_track,download_track,upload_tracks

dbsession = Annotated[AsyncSession, Depends(get_session)]

router = APIRouter(prefix="/tracks", tags=["tracks"])

@router.post("/",summary="Upload Tracks")
async def upload(current_user: Annotated[User, 
                                Security(get_current_active_user, scopes=["user", "admin"])],
                                        session: dbsession, 
                    background_tasks: BackgroundTasks = None,
                    files: list[UploadFile] = File(...), 
                    clean: bool = True
                    )-> dict:
    
    """
    This endpoint allows users to upload one or more track files. The uploaded files are processed in the background
    to extract relevant information and store it in the database.\n\n
    Args:\n
        files (list[UploadFile]): A list of files to be uploaded. This parameter is required.
        clean (bool, optional): A flag indicating whether to clean up temporary files after processing. Defaults to True.
    Returns:\n
        dict: A dictionary containing a message indicating that the tracks are being uploaded and processed in the background.
    """

    contents = {}
    logger.debug(f"Files: {files}")
    for file in files:
                logger.debug(f"Processing file: {file} ")
                contents[file.filename] = await file.read()
             
    background_tasks.add_task(upload_tracks.local_storage, current_user,session,files,contents,clean)

    return {"detail": "Track(s) are being uploaded and processed in the background."}

@router.get("/download",summary="Download All Tracks as zip")
async def download_all(current_user: Annotated[User, 
                                                    Security(get_current_active_user, 
                                                             scopes=["user", "admin"])], 
                            session: dbsession
                        ) -> StreamingResponse:
    """
    Download all tracks for the current user as a ZIP file.
    This asynchronous function retrieves all tracks associated with the current user,
    generates GPX files for each track, and compresses them into a ZIP file for download.\n\n
    Returns:\n
        StreamingResponse: A streaming response containing the ZIP file with all tracks.
            The response has a media type of 'application/zip' and includes a 
            'Content-Disposition' header to prompt the user to download the file.
    Raises:\n
        HTTPException: If no tracks are found for the current user, a 404 error is raised.
    """

    tracks = await get_track.all(current_user.id, session)
    
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for track in tracks:
            logger.info(f"Adding track {track.name} with id {track.id} to the zip file")
            trackpoints = await get_track.points(current_user.id, track.id,session)
            gpx_track = await download_track.gpx_file(track.name, trackpoints)
            zip_file.writestr(f"{track.id}_{track.name}.gpx", gpx_track)
            
    zip_buffer.seek(0)
    
    safe_username = current_user.username.replace('"', '').replace('\r', '').replace('\n', '')
    filename = f"{safe_username}_tracks_{datetime.now().strftime('%Y%m%d')}.zip"

    return StreamingResponse(zip_buffer,
                             media_type='application/zip',
                             headers={'Content-Disposition': f'attachment; filename="{filename}"'})

@router.get("/",response_model=list[TrackSummary],summary="Get track summaries for all tracks")
async def get_tracks( current_user: Annotated[User,
                                                Security(get_current_active_user,
                                                         scopes=["user","admin"])],
                        session: dbsession,
                        limit: Annotated[int, Query(ge=1, le=200, description="Number of tracks to return")] = 50,
                        offset: Annotated[int, Query(ge=0, description="Number of tracks to skip")] = 0,
                    ) -> list[TrackSummary]:
    """
    Fetches track summaries for the current user.\n\n
    Args:\n
        limit (int): Maximum number of tracks to return (1-200). Defaults to 50.
        offset (int): Number of tracks to skip. Defaults to 0.
    Returns:\n
        list[TrackSummary]: A summary of tracks associated with the current user.
    """

    result = await get_track.all(current_user.id, session, limit=limit, offset=offset)

    if result is None:
        raise HTTPException(status_code=404, detail="No tracks found")
    return result

@router.get("/{track_id}",response_model=TrackDetails,summary="Get detailed track information")
async def get_track_info(track_id: int, 
                    
                       current_user: Annotated[User, 
                                               Security(get_current_active_user, 
                                                        scopes=["user", "admin"])], 
                        session: dbsession,
                      
                        ) -> TrackBase:
    
    """
    Retrieve detailed information about a specific track.\n\n
    Args:\n
        track_id (int): The unique identifier of the track to retrieve.
    Returns:\n
        TrackBase: The detailed information of the requested track.
    Raises:\n
        HTTPException: If the track is not found or the user does not have 
            the necessary permissions.
    """
    track = await get_track.details(current_user.id, track_id,session)
    
    return track

@router.delete("/{track_id}",summary="Delete a track")
async def delete(track_id: int, 
                       current_user: Annotated[User, 
                                               Security(get_current_active_user, 
                                                        scopes=["user", "admin"])], 
                        session: dbsession
                        ) -> dict:
   
    """
    Deletes a track based on the provided track ID.\n\n
    Args:\n
        track_id (int): The ID of the track to be deleted.
    Returns:\n
        dict: A dictionary containing a success message indicating the track was deleted.
    Raises:\n
        HTTPException: If the track does not exist or the user does not have the required permissions.
    """

    await get_track.delete(current_user.id, track_id, session)
    return {"message": "Track deleted successfully"}

@router.get("/{track_id}/details",response_model=TrackDetailsWithData,summary="Get detailed track information with data")
async def get_track_details(track_id: int, 
                       current_user: Annotated[User, 
                                               Security(get_current_active_user, 
                                                        scopes=["user", "admin"])], 
                        session: dbsession,
                      
                        ) -> TrackDetailsWithData:
    """
    Retrieve detailed information about a specific track.\n\n
    Args:\n
        track_id (int): The unique identifier of the track to retrieve.
    Returns:\n
        TrackDetailsWithData: An object containing detailed information about the requested track.
    Raises:\n
        HTTPException: If the track is not found or the user does not have the necessary permissions.
    """

    track = await get_track.details(current_user.id, track_id,session)
    return track

@router.get("/{track_id}/points/",response_model=list[TrackPoints],summary="Get all points of a track")
async def get_track_points(track_id: int, 
                            current_user: Annotated[User, 
                                                    Security(get_current_active_user, 
                                                             scopes=["user", "admin"])],
                            session: dbsession,
                            )-> list[TrackPoints]:
    """
    Retrieve all points for a specific track as tuples of (longitude, latitude).\n\n
    Args:\n
        track_id (int): The ID of the track to retrieve points for.
    Returns:\n
        List[Tuple[float, float]]: A list of tuples representing the longitude 
        and latitude of each point in the track as geojson.
    Raises:\n
        HTTPException: If the track is not found or the user does not have 
        permission to access it.
    """
    
    trackpoints = await get_track.points(current_user.id, track_id,session)
    
    return trackpoints

@router.get("/{track_id}/linestring",response_model=TrackLinestring,summary="Get track linestring")
async def get_track_linestring(track_id: int, 
                                current_user: Annotated[User, Security(get_current_active_user,
                                                                        scopes=["user", "admin"])], 
                                session: dbsession
                                ) -> TrackLinestring:
    
    """
    Retrieve the linestring geometry of a specific track as geojson for the current user.\n\n
    Args:\n
        track_id (int): The ID of the track to retrieve.
    Returns:\n
        TrackLinestring: An object containing the linestring geometry of the specified track.
    Raises:\n
        HTTPException: If the track does not exist or the user does not have access to it.
    """

    track = await get_track.linestring(current_user.id, track_id, session)
    track_linestring = TrackLinestring(geometry=track.geometry)

    return track_linestring


@router.get("/{track_id}/download",summary="Download track in GPX format")
async def download(track_id: int, 
                            current_user: Annotated[User, 
                                                    Security(get_current_active_user, 
                                                             scopes=["user", "admin"])], 
                            session: dbsession
                        ) -> StreamingResponse:
    
    """
    Handles the download of a track in GPX format.\n\n
    Args:\n
        track_id (int): The ID of the track to be downloaded.
    Returns:\n
        StreamingResponse: A streaming response containing the GPX file for the requested track, 
        with appropriate headers for file download.
    Raises:\n
        HTTPException: If the track is not found or the user does not have access to it.
    """

    result = await get_track.points(current_user.id,track_id,session)
    result_summary = await session.get(Track, track_id)
    gpx_track = await download_track.gpx_file(result_summary.name,result)
    gpx_track = BytesIO(gpx_track)

    safe_name = result_summary.name.replace('"', '').replace('\r', '').replace('\n', '')
    return StreamingResponse(gpx_track,
                             media_type='application/gpx+xml',
                             headers={'Content-Disposition': f'attachment; filename="{safe_name}.gpx"'})







