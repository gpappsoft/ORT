# Copyright (c) 2025 Marco Moenig (info@moenig.it)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from fastapi import HTTPException, status
from sqlmodel import select
from sqlalchemy.future import select

from passlib.hash import argon2
from datetime import datetime

from app.config import settings
from app.models import User,UserProfile, UserCreate,UserPublic

class GetUser:
    async def by_username(self, 
                     username: str,
                     session,
                     )-> User:
        ''' Search for a user by username '''
        
        query = select(User).filter(User.username == username)
        result = await session.exec(query)
        user = result.scalars().one_or_none()
        
        return user
    
    async def by_email(self, 
                       email: str, 
                       session
                       ) -> User:
        ''' Search for a user by email '''

        query = select(User).filter(User.email == email)
        result = await session.exec(query)
        user = result.scalars().one_or_none()
        return user
    
    async def search(self, 
                     userobj: User,
                     session
                     ) -> User:
        ''' Search for a user by username ''' 
        if "@" in userobj.username:
            return await self.by_email(userobj.username, session)
        return await self.by_username(userobj.username, session)
    
class UserCRUD:    
    async def create(self, 
                     user_data: User, 
                     session
                     ) -> User:
        ''' Create a new user '''

        session.add(user_data)
        await session.commit()
        await session.refresh(user_data)
        return user_data

    async def create_profile(self, 
                             profile_data: UserProfile, 
                             session
                             ) -> UserProfile:
        ''' Create a new user profile '''

        session.add(profile_data)
        await session.commit()
        await session.refresh(profile_data)
        return profile_data
    
    async def update(self, 
                     user_id: int, 
                     user_data: dict, 
                     session
                     ) -> User:
        ''' Update user data '''

        query = select(User).filter(User.id == user_id)
        result = await session.exec(query)
        user = result.scalars().one_or_none()
        if user:
            for key, value in user_data.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            await session.commit()
            await session.refresh(user)
        return user
    
    async def update_profile(self, 
                             user_id: int, 
                             profile_data: dict, 
                             session
                             )-> UserProfile:
        ''' Update user profile data '''
        
        query = select(User).filter(User.id == user_id)
        result = await session.exec(query)
        user = result.scalars().one_or_none()
        if user:
            for key, value in profile_data.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            await session.commit()
            await session.refresh(user)
        return user
    
class UserUtil:
    
    async def password_hash(self, 
                            password: str
                            ) -> str:
            ''' Hash password using argon2 '''

            hashed_password = argon2.hash(password)
            
            return hashed_password
    
    async def register_user(self,
                            user_data: UserCreate, 
                            session
                            ) -> UserPublic:
        ''' Register a new user with profile '''
        
        existing_user = await get_user.by_email(user_data.email, session)
    
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        existing_user = await get_user.by_username(user_data.username, session)
    
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username not available"
            )
        
        
        hashed_password = await user_util.password_hash(user_data.password)
        
        new_profile = UserProfile(
            email=user_data.email,
            firstname=user_data.firstname,
            lastname=user_data.lastname,
            registered_on=datetime.now(),
            confirmed_on=None,
            last_login=None,
        )

        new_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password,
            scopes="user",
            profile=new_profile
        )

        if settings.EMAIL_CONFIRMATION:
            new_user.disabled = True
            
        new_user = await user_crud.create(new_user, session)

        return new_user
    
get_user = GetUser() 
user_crud = UserCRUD()
user_util = UserUtil()
