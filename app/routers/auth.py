# Copyright (c) 2025 Marco Moenig (info@moenig.it)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT


from fastapi import APIRouter, Depends, Request, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from sqlmodel.ext.asyncio.session import AsyncSession
from passlib.context import CryptContext
from loguru import logger
from datetime import timedelta
from app.models import User
from app.lib.auth import create_access_token,Token
from app.db import get_session
from app.lib.users import get_user
from app.config import settings
from app.lib.ratelimit import check_rate_limit

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
dbsession = Annotated[AsyncSession, Depends(get_session)]

router = APIRouter(prefix="/auth", tags=["auth"])

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

@router.post("/login",tags=["auth"])
async def login(request: Request,
                form_data: Annotated[OAuth2PasswordRequestForm,
                                     Depends()],
                session: dbsession
                ) -> Token:
    
    """
    Handles user login by validating credentials and generating an access token.\n\n
    Args:\n
        form_data (OAuth2PasswordRequestForm): The form data containing the username and password.
    Returns:\n
        Token: An object containing the access token and its type.
    Raises:\n
        HTTPException: If the username or password is incorrect, or if the user is disabled.
    """
    
    check_rate_limit(request.client.host if request.client else "unknown", max_attempts=10, window_seconds=60)
    logger.debug(f"User {form_data}")
    user = User(username=form_data.username)
    
    userobj = await get_user.search(user, session=session)
    if not userobj or not verify_password(form_data.password, userobj.password_hash) or userobj.disabled == True:
     raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=("Incorrect username or password"),
        )
    logger.debug(f"User found: {userobj.email} with id: {userobj.id} with scopes: {userobj.scopes}")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    raw_scopes = userobj.scopes or ""
    scopes = [s.strip() for s in raw_scopes.split(",") if s.strip()] if isinstance(raw_scopes, str) else raw_scopes
    access_token = await create_access_token(data={"sub": userobj.email, "scopes": scopes}, expires_delta=access_token_expires)
    logger.debug("Token created for user: {user}", user=userobj.email)

    return Token(access_token=access_token, token_type="bearer")

