# Copyright (c) 2025 Marco Moenig (info@moenig.it)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT


from fastapi import HTTPException, UploadFile
from sqlmodel import select
from pathlib import Path
from loguru import logger
from geoalchemy2.functions import ST_MakePoint

from PIL import Image as PILImage
from io import BytesIO
from hashlib import md5
from app.models import Images,ImageComment,ImageSummary,User
from app.exceptions import CustomException
from app.config import settings



def check_image(image: Images,user_id: int):
    ''' 
    Check if the user has access to the image and is not none
    '''
    logger.debug(f"Image: {image}")
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if image.user_id != user_id:
        raise HTTPException(status_code=404, detail="You have no access to this image")
    
    return
   
class ImageComment:
    async def get_comments(self, 
                           image_id: int,
                           session) -> list[ImageComment]:
        ''' Get all comments for an image '''
        query = select(ImageComment).filter(ImageComment.image_id == image_id)
        result = await session.exec(query)
        comments = result.scalars().all()
        return comments
    
class Image:     
    async def all(self,
                        user_id: int,
                        session,
                        limit: int = 50,
                        offset: int = 0,
                        )-> list[ImageSummary]:
        ''' Get all images as summary '''

        query = select(Images).filter(Images.user_id == user_id).order_by(Images.created_at.desc()).offset(offset).limit(limit)

        result = await session.exec(query)
        images = result.unique().all()

        if not images:
            raise CustomException("No Images found", status_code=404)

        return images
   
    async def convert_to_degress(self,
                                 value
                                 ) -> float:
        ''' 
        Convert GPS coordinates from degrees, minutes, seconds to decimal 
        '''

        d = float(value.values[0].num) / float(value.values[0].den)
        m = float(value.values[1].num) / float(value.values[1].den)
        s = float(value.values[2].num) / float(value.values[2].den)
        
        degrees = ((((d*60) + m)*60) + s) / 60 / 60
                    
        # Convert to float for precise calculations
        # degrees = float(degrees)

        return degrees
    
    async def scale_images(self,
                           contents
                           ) -> bytes:
        ''' Scale images and create thumbnail '''
        image = PILImage.open(BytesIO(contents))
        
        output = BytesIO()
        output_thump = BytesIO()

        image.save(output, format="webp", quality=70)
        
        size = (128, 128)
        image.thumbnail(size)
        
        image.save(output_thump, format="webp", quality=80)
        return (output.getvalue(),output_thump.getvalue())
        
    
    async def track_images(self, 
                           user_id: int,
                           track_id: int, 
                           session
                           ) -> list[Images]:
        ''' Get all images for a track '''
        query = select(Images).filter(Images.track_id == track_id).filter(Images.user_id == user_id).order_by(Images.created_at)
        
        images = await session.exec(query)
        images = images.unique().all()

        if not images:
            raise CustomException("No Images found or you do not have access to this image",status_code=404)
        
        # for image in images:
        #     image.comments = await get_image_comment.get_comments(image.id, session)

        
        logger.debug(f"Images: {images}")
        return images
    
    async def image_by_id(self, 
                    user_id: int, 
                    image_id: int, 
                    session
                    ) -> Images:
        ''' Get image by image ID '''
        query = select(Images).filter(Images.id == image_id).filter(Images.user_id == user_id)
        
        
        image = await session.exec(query)
        image = image.unique().one_or_none()
        
        return image
    
    async def image_by_md5(self, 
                           user_id: int,
                           md5_hash: str, 
                           session
                           ) -> Images:
        query = select(Images).filter(Images.md5_hash == md5_hash).filter(Images.user_id == user_id)
        
        image = await session.exec(query)
        image = image.unique().one_or_none()       

        return image
    
class UploadImages:
    async def local_storage(self,current_user: User,
                               session,files: list[UploadFile],
                               contents: dict,
                               tags: dict,
                               track:int) -> dict:       
        try:
            stored_files = []
            skipped_files = {}

            for file in files:
                
                # Create subdirectory with the user's UUID
                try:
                    user_uuid = current_user.uid
                    user_dir_thumbs = Path(f"{settings.IMAGE_PATH}/{user_uuid}/thumbs")
                    user_dir_thumbs.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    logger.error(f"Failed to create directory: {e}")
                    raise CustomException("Failed to create user image directory",status_code=500)
                
                # Generate MD5 hash of the file contents
                md5_hash = md5(contents[file.filename]).hexdigest()
                #file_extension = Path(file.filename).suffix
                #hashed_filename = f"{md5_hash}{file_extension}"
                hashed_filename = f"{md5_hash}.webp"
                # # Check if the MD5 hash already exists in the database
                existing_image = await image.image_by_md5(current_user.id, md5_hash, session)
                
                # Check if the file already exists in the filesystem
                if existing_image:
                    logger.warning(f"Image with hash {md5_hash} already exists. Skipping file {file.filename}.")
                    skipped_files[f"{file.filename}"] = "file exists"
                    continue
                
                # Check if the file is an image
                if not file.content_type.startswith("image/"):
                    logger.warning(f"File {file.filename} is not an image. Skipping.")
                    skipped_files[f"{file.filename}"] ="no image"
                    continue
                # Check if the file size is too large
                if len(contents[file.filename]) > settings.MAX_IMAGE_SIZE:
                    logger.warning(f"File {file.filename} is too large. Skipping.")
                    skipped_files[f"{file.filename}"] ="too large"
                    continue
                # Check if the file is empty
                if len(contents[file.filename]) == 0:
                    logger.warning(f"File {file.filename} is empty. Skipping.")
                    skipped_files[f"{file.filename}"] ="empty file"
                    continue
                
                # Scale the image
                (scaled_contents,scaled_contents_thump) = await image.scale_images(contents[file.filename])
                
                file_path = Path(f"{settings.IMAGE_PATH}/{user_uuid}/") / hashed_filename
                file_path_thumb = user_dir_thumbs / hashed_filename
                
                with open(file_path_thumb, "wb") as f:
                    f.write(scaled_contents_thump)
                with open(file_path, "wb") as f:
                    f.write(scaled_contents)
                
                new_image = Images(filename=file.filename, user_id=current_user.id, md5_hash=md5_hash)
            
                if track:
                    new_image.track_id = track

                if "GPS GPSLatitude" in tags[file.filename] and "GPS GPSLongitude" in tags[file.filename]:
                    logger.info("GPS data found")
                    lat_ref = tags[file.filename]["GPS GPSLatitudeRef"].values
                    lon_ref = tags[file.filename]["GPS GPSLongitudeRef"].values
                    lat=tags[file.filename]["GPS GPSLatitude"]
                    lon=tags[file.filename]["GPS GPSLongitude"]
                    
                    lat = await image.convert_to_degress(tags[file.filename]["GPS GPSLatitude"])
                    lon = await image.convert_to_degress(tags[file.filename]["GPS GPSLongitude"])
                    
                    if lat_ref != "N":
                        lat = -lat
                    if lon_ref != "E":
                        lon = -lon
                    new_image.geometry = f"SRID=4326;POINT({lon} {lat})"
                
                session.add(new_image)
                stored_files.append(hashed_filename)
            
            await session.commit()
            #return {"Stored images with filenames": stored_files, "skipped images": skipped_files}
        
        except Exception as e:
            logger.error(f"Failed to upload images: {e}")
            raise CustomException("Failed to upload images",status_code=500)

class UpdateImages:
    async def data(self,
                    current_user: User,
                    image_id: int,
                    imageUpdate,
                    
                    session
                    ) -> Images:
        ''' Update image metadata '''
        
        query = select(Images).filter(Images.id == image_id).filter(Images.user_id == current_user.id)
        
        image = await session.exec(query)
        image = image.unique().one_or_none()      

        if not image or image.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Image not found or not authorized to update this image")
        
        setattr(image, "geometry", ST_MakePoint(imageUpdate.lon, imageUpdate.lat))

        for key, value in imageUpdate.model_dump().items():
            if value is not None and key != "lat" and key != "lon":
                setattr(image, key, value) 
        
        
        session.add(image)
        
        await session.commit()
        await session.refresh(image)

        return image
    
image_comment = ImageComment() 
image = Image()
upload_images = UploadImages()
update_image = UpdateImages()
