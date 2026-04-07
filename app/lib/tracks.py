# Copyright (c) 2025 Marco Moenig (info@moenig.it)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT


from fastapi import HTTPException,UploadFile
from sqlmodel import select
from sqlalchemy.future import select
from geoalchemy2.functions import ST_GeomFromEWKT
from geoalchemy2.shape import to_shape
from shapely.geometry import LineString
import numpy as np
from gpxpy import parse
import gpxpy
from scipy.signal import savgol_filter
from pathlib import Path
from loguru import logger

from app.models import User,Track,TrackPoint,TrackPoints,TrackSummary,TrackWaypoint
from app.exceptions import CustomException

def check_track(track: Track,user_id: int):
    ''' 
    Check if the user has access to the track and is not none
    '''

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if track.user_id != user_id:
        raise HTTPException(status_code=404, detail="You have no access to this track")
    
    return
   
class GetTrack:
    async def all(self,
                         user_id: int,
                         session,
                         limit: int = 50,
                         offset: int = 0,
                         )-> list[TrackSummary]:
        ''' Get all tracks for a user '''

        query = select(Track).filter(Track.user_id == user_id).order_by(Track.created_at.desc()).offset(offset).limit(limit)

        result = await session.exec(query)
        tracks = result.unique().scalars().all()

        if not tracks:
            return None

        return tracks
        
    async def details(self,
                        user_id: int,
                        track_id: int,
                        session
                        ) -> Track:
            ''' Get track details '''
            
            query = select(Track).filter(Track.user_id == user_id, Track.id == track_id)
            result = await session.exec(query)
            track = result.unique().scalars().one_or_none()
            check_track(track,user_id)

            return track
            
    
    async def delete(self,
                        user_id: int,
                        track_id: int,
                        session,
                        ) -> None:
        ''' Delete a track '''      
        track = await self.details(user_id, track_id,session)
        check_track(track,user_id)
    
        await session.delete(track)
        await session.commit()

        return
    
    async def points(self, 
                         user_id: int, 
                         track_id: int, 
                         session, 
                         )-> list[TrackPoints]:
        ''' Get track points for a track '''
        query = select(TrackPoint).filter(TrackPoint.track_id == track_id,TrackPoint.user_id == user_id)
        
        result = await session.exec(query)
        trackpoints = result.unique().scalars().all()

        if not trackpoints:
            raise HTTPException(status_code=404, detail="No points found for this track")
        
        return trackpoints
    
    async def linestring(self, 
                             user_id: int, 
                             track_id: int, 
                             session
                             ) -> str:
        ''' Get the linestring representation of a track '''

        track = await session.get(Track, track_id)
        check_track(track,user_id)

        return track
    
    async def clean_track(self, 
                          user_id: int, 
                          track_id: int, 
                          session, 
                          resample_interval: float, 
                          points: dict = None
                          ) -> LineString:
        ''' Clean and resample a track '''
        
        if points is None:
            track = await session.get(Track, track_id)
            check_track(track,user_id)

            # Fetch track points from the database
            query = select(TrackPoint.longitude, TrackPoint.latitude).filter(TrackPoint.track_id == track_id)
            result = await session.exec(query)
            points = result.all()

            if not points:
                raise HTTPException(status_code=404, detail="No points found for this track")

            # Extract coordinates
            coords = np.array([(point.longitude, point.latitude) for point in points])
        else:
            # Use provided points
            coords = np.array([(point[0], point[1]) for point in points])

        # Smooth the coordinates using Savitzky-Golay filter
        smoothed_coords = savgol_filter(coords, window_length=5, polyorder=2, axis=0)

        # Resample the track
        def resample_line(line, interval):
            length = line.length
            num_points = int(length / interval)
            return LineString([line.interpolate(float(i) / num_points, normalized=True) for i in range(num_points + 1)])

        # Reduce the number of points todo!
        def reduce_points(coords, tolerance):
            line = LineString(coords)
            simplified_line = line.simplify(tolerance, preserve_topology=True)
            return np.array(simplified_line.coords)

        
        smoothed_line = LineString(smoothed_coords)
        resampled_line = resample_line(smoothed_line, resample_interval)
        tolerance = 0.0001  # Adjust the tolerance as needed
        resampled_line = reduce_points(resampled_line, tolerance)
        
        if points is None:
            # Update the track geometry
            track.geometry = 'SRID=4326;' + resampled_line.wkt
            session.add(track)
            await session.commit()

        return resampled_line

        
class DownloadTrack:
    async def gpx_file(self, 
                       track_name: str,
                       track_points: list[TrackPoints],
                       ) -> bytes:
        ''' 
        Create a GPX file from track points. Returns the GPX file as bytes.
        '''
        
        # Create GPX file
        gpx = gpxpy.gpx.GPX()
        gpx_track = gpxpy.gpx.GPXTrack(name=track_name)
        gpx.tracks.append(gpx_track)
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)
        
        for point in track_points:
            v = to_shape(point.geometry)
            gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(longitude=v.x, latitude=v.y))
        
        return gpx.to_xml().encode('utf-8')
        
class UploadTracks:
    async def local_storage(self,current_user: User,
                               session,files: list[UploadFile],
                               contents: dict,
                               clean: bool,
                               ) -> dict:      
        try:
            files_stored = []
            files_skipped = []

            for file in files:
                
                try:
                    gpx = parse(contents[file.filename].decode(encoding="utf-8"))
                except Exception as e:
                    files_skipped.append(file.filename)
                    continue
                    
                waypoints = {}
                points = {}
                
                for waypoint in gpx.waypoints:
                    waypoints[waypoint.name] = {
                        "longitude": waypoint.longitude,
                        "latitude": waypoint.latitude,
                        "time": waypoint.time,
                        "description": waypoint.description,
                        "type": waypoint.type
                    }
                
                for track in gpx.tracks:
                    for segment in track.segments:
                        for point in segment.points:
                            points[(point.longitude, point.latitude)] = (point.elevation, point.speed, point.time)

                if not points:
                    raise HTTPException(status_code=400, detail="No valid points found in the GPX file")
                
                if clean:
                    resampled_points = await get_track.clean_track(current_user.id, None, session, 0.01, points)
                else:
                    resampled_points = list(points.keys())
                
                linestring = LineString(resampled_points)
                wkt_linestring = 'SRID=4326;' + str(linestring)
                
                track = Track(name=Path(file.filename).stem, user_id=current_user.id, geometry=ST_GeomFromEWKT(wkt_linestring))
                
                session.add(track)
                await session.commit()
                await session.refresh(track)

                for (longitude,latitude), (elevation, speed, time) in points.items():
                    track_point = TrackPoint(track_id=track.id, 
                                            user_id=current_user.id,
                                            geometry=f'SRID=4326;POINT({longitude} {latitude})', 
                                            elevation=elevation, time=time)
                    session.add(track_point)
                
                for name, waypoint in waypoints.items():
                    track_point = TrackWaypoint(track_id=track.id, 
                                                geometry=f'SRID=4326;POINT({waypoint["longitude"]} {waypoint["latitude"]})',
                                                elevation=waypoint["elevation"],
                                                speed=waypoint["speed"], 
                                                time=waypoint["time"], 
                                                name=name, description=waypoint["description"], 
                                                type=waypoint["type"])
                    session.add(track_point)

                await session.commit()
                files_stored.append(file.filename)
            
        #return {"GPX track uploaded and stored successfully:": [files_stored], "Skipped files": [files_skipped]}
        except Exception as e:
            logger.error(f"Failed to upload images: {e}")
            raise CustomException(status_code=500, detail="Failed to upload tracks")
    
download_track = DownloadTrack()        
get_track  = GetTrack() 
upload_tracks = UploadTracks()

