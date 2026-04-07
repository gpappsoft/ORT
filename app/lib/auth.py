# Copyright (c) 2025 Marco Moenig (info@moenig.it)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from fastapi import Depends, HTTPException, Security,status
from fastapi.security import SecurityScopes,OAuth2PasswordBearer
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import Annotated
from pydantic import BaseModel,ValidationError

from loguru import logger
from jwt import encode, decode
from jwt.exceptions import InvalidTokenError
from datetime import datetime, timedelta, timezone

from app.models import User
from app.lib.users import get_user
from app.db import get_session
from app.lib.cache import cache
from app.config import settings


oauth2_scheme = OAuth2PasswordBearer(settings.TOKEN_URL)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: str | None = None
    scopes: list[str] = []

async def create_access_token(data: dict, 
                        expires_delta: timedelta | None = None
                        ) -> str:
    '''Create a new access token with the given data and expiration time'''
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user( security_scopes: SecurityScopes, 
                            token: Annotated[str, 
                                             Depends(oauth2_scheme)],
                            session: AsyncSession = Depends(get_session)
                            ) -> User:
    '''Get the current user from cache/database and check if the user has the required scopes'''
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )
    try:
        payload = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")

        if username is None:
            raise credentials_exception
        logger.debug(f"Username: {username}")    
        user = await cache.get_object(username)
  
        if user:
              user = User.model_validate_json(user)
        else:
            user = User(username=username)
            user = await get_user.search(user, session)
            await cache.set_object(username, user.model_dump_json())
            
        raw_scopes = user.scopes or ""
        token_data = TokenData(scopes=[s.strip() for s in raw_scopes.split(",") if s.strip()], username=username)

    except (InvalidTokenError, ValidationError):
        raise credentials_exception
    
    if user is None:
        raise credentials_exception
    
    for scope in security_scopes.scopes:
        if scope in token_data.scopes:
            logger.info("Access "+ str(security_scopes.scopes))
            return user
        
    logger.info("Not enough permission user: {user} id: {id} have: {userscopes} wants: {wscopes}",user=user.username,id=user.uid,userscopes=user.scopes,wscopes=scope)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Permission denied",
        headers={"WWW-Authenticate": authenticate_value},
    )
    

async def get_current_active_user( current_user: Annotated[User, 
                                                           Security(get_current_user)]
                                  ) -> User:
    '''Check if the current user is
    - authenticated
    - active
    '''
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
    
