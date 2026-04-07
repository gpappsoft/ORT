# Copyright (c) 2025 marco
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT


from sqlmodel import SQLModel, Field, Column, Relationship
from typing import Any, Optional,List,Annotated
from pydantic import field_validator,AfterValidator, model_validator
import re
import sqlalchemy as sa
from datetime import datetime
from uuid import UUID, uuid4
from geoalchemy2 import Geometry,WKBElement
from geoalchemy2.shape import to_shape
from shapely import to_geojson,LineString
from loguru import logger
import json 

def geom_geojson(v: WKBElement | None) -> WKBElement | None:
    if v is not None:
        v = to_geojson(to_shape(v))
        return json.loads(v)
    return None

class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    email: str | None = Field(nullable=False, unique=True)
    
class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    uid: UUID = Field(default_factory=uuid4, unique=True, index=True, nullable=False)
    password_hash: str | None = Field(nullable=False, exclude=True)
    disabled: bool | None = Field(default=False)
    scopes: str | None = Field(default="user")

    #track: Optional[list["Track"]] = Relationship(back_populates="user", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    #images: Optional[list["Images"]] = Relationship(back_populates="user", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    profile: Optional["UserProfile"] = Relationship(back_populates="user", sa_relationship_kwargs={"cascade": "all, delete-orphan",'lazy': 'joined'})

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class UserCreate(SQLModel):
    username: str = Field(min_length=3, max_length=50)
    email: str
    password: str = Field(min_length=8)
    firstname: str | None = None
    lastname: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v.lower()

class UserProfileBase(SQLModel):    
    firstname: str | None = Field()
    lastname: str | None = Field()
    registered_on: datetime = Field(nullable=True)
    last_login: datetime = Field( nullable=True)

class UserProfile(UserProfileBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id")
    confirmed: bool | None = Field(default=False)
    confirmed_on: datetime = Field(nullable=True)
    
    user: Optional[User] = Relationship(back_populates="profile")

class UserPublic(SQLModel):
    username: str
    email: str
    profile: Optional["UserProfileBase"] = None     

class TrackBase(SQLModel):
    name: str
    geometry: Any = Field(sa_column=Column(Geometry('LINESTRING', srid=4326)))
    start_time: Optional[datetime] | None = Field()
    end_time: Optional[datetime] | None = Field()
    created_at: datetime = Field(default_factory=datetime.now)
    
    
class Track(TrackBase, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, nullable=False, foreign_key="user.id")
    is_public: bool = Field(default=False)
    
    #user: User | None = Relationship(back_populates="track")
    comments: Optional[list["TrackComment"]] = Relationship(back_populates="track", sa_relationship_kwargs={"cascade": "all, delete-orphan",'lazy': 'joined'})
    images: Optional[list["Images"]] = Relationship(back_populates="track", sa_relationship_kwargs={"cascade": "all, delete-orphan",'lazy': 'joined'})
    #points: list["TrackPoint"] = Relationship(back_populates="track", sa_relationship_kwargs={"cascade": "all, delete-orphan", 'lazy': 'joined'})
    waypoints: Optional[list["TrackWaypoint"]] = Relationship(back_populates="track", sa_relationship_kwargs={"cascade": "all, delete-orphan",'lazy': 'joined'})

class TrackComment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id")
    track_id: int | None = Field(default=None, foreign_key="track.id")
    content: str
    created_at: datetime = Field(default_factory=datetime.now)

    user: User | None = Relationship()
    track: Track | None = Relationship(back_populates="comments")

class TrackCommentSummary(SQLModel):
    content: str
    created_at: datetime

class TrackSummary(SQLModel):
    id: int
    name: str
    created_at: datetime

class TrackDetails(TrackBase):
    comments: Optional[list[TrackCommentSummary]] = None 
    geometry: Annotated[Any, AfterValidator(geom_geojson)] = Field(sa_column=Column(Geometry('LINESTRING', srid=4326)))

class TrackDetailsWithData(TrackBase):
    geometry: Annotated[Any, AfterValidator(geom_geojson)] = Field(sa_column=Column(Geometry('LINESTRING', srid=4326)))
    waypoints: Optional[list["TrackWaypoint"]] = None
    images: Optional[list["ImageWithComments"]] = None
    comments: Optional[list[TrackCommentSummary]] = None 
    
class TrackLinestring(SQLModel):
    geometry: Annotated[Any, AfterValidator(geom_geojson)] = Field(sa_column=Column(Geometry('LINESTRING', srid=4326)))
    
class TrackPointBase(SQLModel):
    geometry: Any = Field(sa_column=Column(Geometry('POINT', srid=4326)))
    altitude: Optional[float] | None
    speed: Optional[float] | None 
    timestamp: datetime = Field(default_factory=datetime.now)
    
class TrackPoint(TrackPointBase,table=True):
    id: int = Field(default=None, primary_key=True)
    track_id: int = Field(foreign_key="track.id")
    user_id: int = Field(foreign_key="user.id")
    
class TrackPoints(SQLModel):
    geometry: Annotated[Any, AfterValidator(geom_geojson)] = Field(sa_column=Column(Geometry('POINT', srid=4326)))
    altitude: Optional[float] | None
    speed: Optional[float] | None
    timestamp: datetime = Field(default_factory=datetime.now)
    
class TrackWaypoint(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    track_id: int = Field(default=None, foreign_key="track.id")
    geometry: Any = Field(sa_column=Column(Geometry('POINT', srid=4326)))
    altitude: float | None = Field()
    speed: float | None = Field()
    name: str | None = Field()
    description: str | None = Field()
    type: str | None = Field()
    timestamp: datetime | None = Field()

    track: Track | None = Relationship(back_populates="waypoints")
    
class RealtimePosition(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id",unique=True)
    geometry: Annotated[Any, AfterValidator(geom_geojson)] = Field(sa_column=Column(Geometry('POINT', srid=4326)))
    timestamp: datetime = Field(default_factory=datetime.now)

    user: User = Relationship()

class ImageBase(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    md5_hash: str | None = Field(unique=True, index=True, nullable=False)
    geometry: Annotated[Any, AfterValidator(geom_geojson)] = Field(sa_column=Column(Geometry('POINT', srid=4326)))
              
class Images(ImageBase, table=True, mutable=True):
    user_id: int | None = Field(default=None, foreign_key="user.id")
    track_id: int | None = Field(default=None, foreign_key="track.id")
    created_at: datetime = Field(default_factory=datetime.now)
    is_public: bool = Field(default=False)
    filename: str
    
    #user: User | None = Relationship(back_populates="images")
    track: Track | None = Relationship(back_populates="images")
    comments: list["ImageComment"] = Relationship(back_populates="images", sa_relationship_kwargs={"cascade": "all, delete-orphan",'lazy': 'joined'})

class ImageComment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id")
    image_id: int | None = Field(default=None, foreign_key="images.id")
    content: str
    created_at: datetime = Field(default_factory=datetime.now)

    user: User | None = Relationship()
    images: Images | None = Relationship(back_populates="comments")

class ImageCommentSummary(SQLModel):
    content: str
    created_at: datetime = Field(default_factory=datetime.now)

class ImageSummary(SQLModel):
    id: int
    filename: str
    created_at: datetime
    is_public: bool
    geometry: Annotated[Any, AfterValidator(geom_geojson)] = Field(sa_column=Column(Geometry('POINT', srid=4326)))
    
class ImageWithComments(ImageSummary):
    comments: list[ImageCommentSummary]

class ImageSummaryWithData(SQLModel):
    md5_hash: str
    geometry: Annotated[Any, AfterValidator(geom_geojson)] = Field(sa_column=Column(Geometry('POINT', srid=4326)))
    is_public: bool
    created_at: datetime
    filename: str

class ImageUpdate(SQLModel):
    is_public: bool | None = None
    track_id: int | None = None
    lat: float | None = None
    lon: float | None = None
    



