# Copyright (c) 2025 Marco Moenig (info@moenig.it)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT


import os


from fastapi import APIRouter, HTTPException, UploadFile, BackgroundTasks, File, Form, Depends, Security, Query
from typing import Annotated, Union

from sqlalchemy.future import select
from sqlmodel.ext.asyncio.session import AsyncSession
from pathlib import Path
from exifread import process_file
from loguru import logger

from app.db import get_session
from app.models import ImageBase, Images, ImageUpdate, ImageSummary, ImageWithComments, ImageSummaryWithData, User
from app.config import settings
from app.lib.images import image, upload_images,update_image
from app.lib.auth import get_current_active_user


dbsession = Annotated[AsyncSession, Depends(get_session)]

router = APIRouter(prefix="/images", tags=["images"])

@router.post("/{track_id}",response_model=dict,summary="Upload images")
async def store_images(current_user: Annotated[User, 
                            Security(get_current_active_user, 
                                     scopes=["user", "admin"])],
                        track_id: int,
                        session: dbsession, 
                        files: list[UploadFile] = File(...),
                        background_tasks: BackgroundTasks = None,
                        
                        ) -> dict:
    '''
    Upload one or more image files and extract GPS location data if available.
    The filenames are hashed and stored in the database as md5. The files are saved in the filesystem.
    Original filenames are stored in the database.
    Optionally, associate images with a track ID if provided in the request.\n\n
    Args:\n
        files: List of image files to upload.
        track_id (int): The ID of the track to associate the images with.
    Returns:\n
        dict: A dictionary containing the status of the upload operation.
    Raises:\n
        HTTPException: If the user is not found (HTTP 404) or if the user is disabled (HTTP 403).
    '''
    contents = {}
    tags = {}

    for file in files:
                logger.debug(f"Processing file: {file} ")
                contents[file.filename] = await file.read()
                tags[file.filename] = process_file(file.file)

    background_tasks.add_task(upload_images.local_storage, current_user,session,files,contents,tags,track_id)

    return {"detail": "Images are being uploaded and processed in the background."}

@router.get("/",response_model=list[ImageSummary],summary="Get a list of image summaries")
async def get_images(current_user: Annotated[User,
                                            Security(get_current_active_user,
                                                     scopes=["user", "admin"])],
                    session: dbsession,
                    limit: Annotated[int, Query(ge=1, le=200, description="Number of images to return")] = 50,
                    offset: Annotated[int, Query(ge=0, description="Number of images to skip")] = 0,
                    ) -> list[ImageSummary]:
    """
    Retrieve a list of image summaries for the current user.\n\n
    Args:\n
        limit (int): Maximum number of images to return (1-200). Defaults to 50.
        offset (int): Number of images to skip. Defaults to 0.
    Returns:\n
        list[ImageSummary]: A list of image summaries associated with the current user.
    Raises:\n
        HTTPException: If the user is not authenticated or lacks the required scopes.
    """
    images = await image.all(current_user.id, session, limit=limit, offset=offset)

    return images

@router.get("/{image_id}",response_model=ImageWithComments,summary="Get an image with comments")
async def get_image(current_user: Annotated[User, 
                                             Security(get_current_active_user, 
                                                      scopes=["user", "admin"])],
                    session: dbsession, 
                    image_id: Union[int, str],
                    type: Annotated[str | None, 
                                    Query(  title="Search type",
                                            description="Defines the type of search for an image. Supported types are 'id' and 'md5'",)] = 'md5',
                    ) -> ImageWithComments:
    
    """
    Retrieve an image with its associated comments based on the specified search type.\n\n
    Args:\n
        image_id (str): The identifier of the image to retrieve. Defaults to None.
        type (int|str): The type of search to perform. Supported types are:
            - 'md5': Search by the MD5 hash of the image.
            - 'id': Search by the numeric ID of the image.
            Defaults to 'md5'.
    Returns:\n
        ImageWithComments: The image object along with its associated comments.
    Raises:\n
        HTTPException: If the search type is not supported (status code 404).
        HTTPException: If the image is not found or the user is not authorized to access it (status code 404).
    """

    if type == 'md5':
        images = await image.image_by_md5(current_user.id, image_id, session)
    elif type == 'id':
        images = await image.image_by_id(current_user.id, int(image_id), session)
    else:
        raise HTTPException(status_code=404, detail="Search type not supported")
    
    if not images:
        raise HTTPException(status_code=404, detail="Image not found or not authorized to access this image")
    
    return images


@router.put("/{image_id}", response_model=ImageSummaryWithData,summary="Update image data")
async def update_image_data( image_id: int,
                        current_user: Annotated[User, 
                                                Security(get_current_active_user, 
                                                        scopes=["user", "admin"])],
                        session: dbsession,
                        imageUpdate: Annotated[ImageUpdate, Form()],
                        ) -> dict:
    """
    Update image data for a specific image.\n\n
    Args:\n
        image_id (int): The ID of the image to be updated.
        imageUpdate (ImageUpdate): The updated image data provided via a form.
    Returns:\n
        dict: A dictionary containing the result of the update operation.
    Raises:\n
        HTTPException: If an error occurs during the update process.
    """ 
    try:
        result = await update_image.data(current_user, image_id, imageUpdate,session)
    
        return result

    except Exception as e:
        logger.error(f"Failed to update image with ID {image_id} for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update image")

@router.delete("/{image_id}",summary="Delete an image")
async def delete_image( image_id: int,
                        current_user: Annotated[User, 
                                                Security(get_current_active_user, 
                                                        scopes=["user", "admin"])],
                        session: dbsession,
                        ) -> dict:
    """
    Deletes an image from the database and storage.\n\n
    Args:\n
        image_id (int): The ID of the image to be deleted.
    Returns:\n
        dict: A dictionary containing a success message.
    Raises:\n
        HTTPException: If the image is not found, the user is not authorized to delete it, 
                        or an error occurs during the deletion process.
    Notes:\n
        - The function first checks if the image exists in the database and if the current user 
            is authorized to delete it.
        - Deletes the image record from the database and commits the transaction.
        - Attempts to remove the image file and its thumbnail from the filesystem. 
            If the files do not exist, the errors are ignored.
    """

    try:
        db_image = await image.image_by_id(current_user.id,image_id,session)

        logger.debug(f"Deleting image: {db_image}")

        # Build and validate paths before committing the DB delete
        base_dir = Path(settings.IMAGE_PATH).resolve()
        user_dir = (base_dir / str(current_user.uid)).resolve()
        user_dir_thumbs = (user_dir / "thumbs").resolve()
        file_extension = Path(db_image.filename).suffix
        image_path = (user_dir / f"{db_image.md5_hash}{file_extension}").resolve()
        thumb_path = (user_dir_thumbs / f"{db_image.md5_hash}{file_extension}").resolve()

        if not image_path.is_relative_to(base_dir) or not thumb_path.is_relative_to(base_dir):
            raise HTTPException(status_code=400, detail="Invalid file path")

        await session.delete(db_image)
        await session.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete image {image_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete image")

    try:
        os.remove(image_path)
    except OSError:
        pass
    try:
        os.remove(thumb_path)
    except OSError:
        pass

    finally:
        logger.debug("Cleanup operations completed.")
    return {"detail": "Image deleted successfully"}
    
@router.get("/track/{track_id}",response_model=list[ImageSummaryWithData],summary="Get all images aossociated with a track")
async def get_images_by_track( current_user: Annotated[User, 
                                                        Security(get_current_active_user, 
                                                                scopes=["user", "admin"])],
                                session: dbsession, 
                                track_id: int = None
                            ) -> list[ImageBase]:
    """
    Retrieve images associated with a specific track for the current user.\n\n
    Args:\n
        track_id (int, optional): The ID of the track to retrieve images for. Defaults to None.
    Returns:\n
        list[ImageBase]: A list of images associated with the specified track.
    Raises:\n
        HTTPException: If the user is not authorized or if an error occurs during the retrieval process.
    """
    images = await image.track_images(current_user.id,track_id, session)
    return images

@router.get("/track/{track_id}/details",response_model=list[ImageWithComments],summary="Get all images, including comments, aossociated with a track")
async def get_images_by_track_with_comments( current_user: Annotated[User, 
                                                        Security(get_current_active_user, 
                                                                scopes=["user", "admin"])],
                                session: dbsession, 
                                track_id: int = None
                            ) -> list[ImageBase]:
    """
    Fetches images associated with a specific track along with comments for the current user.\n\n
    Args:\n
        track_id (int, optional): The ID of the track for which images are to be fetched. Defaults to None.
    Returns:\n
        list[ImageBase]: A list of images associated with the specified track.
    """
    images = await image.track_images(current_user.id,track_id, session)
    
    return images
