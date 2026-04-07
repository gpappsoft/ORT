# Copyright (c) 2025 Marco Moenig (info@moenig.it)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT


from fastapi import status, APIRouter, Depends, Request, Security, Form
from typing import Annotated
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import UserCreate, UserPublic
from app.lib.auth import get_current_active_user
from app.db import get_session
from app.config import settings
from app.lib.users import user_util, get_user
from app.exceptions import CustomException
from app.lib.ratelimit import check_rate_limit

dbsession = Annotated[AsyncSession, Depends(get_session)]

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/",response_model=UserPublic,tags=["users"])
async def read_own_users(current_user: Annotated[ UserPublic, 
                                                 Security(get_current_active_user, 
                                                          scopes=["admin","user"])],
                            session: dbsession
                        ) -> UserPublic:
    """
    Retrieve the details of the currently authenticated user.
    This function fetches the user information for the currently authenticated 
    user based on the provided security scopes. It ensures that the user exists 
    and is not disabled before returning the user details.\n\n
    Returns:\n
        UserPublic: The details of the authenticated user.
    Raises:\n
        CustomException: If the user is not found (HTTP 404) or if the user is 
            disabled (HTTP 403).
    """
    user = await get_user.search(current_user,session=session)
    if not user:
        raise CustomException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user.disabled == True:
        raise CustomException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is disabled",
        )
    return  user

@router.post("/register", response_model=UserPublic)
async def register_user(request: Request,
                        session: dbsession,
                        user_data: Annotated[UserCreate, Form()] = None,
                        ):
    
    """
    Registers a new user in the system.\n\n
    Args:\n
        UserCreate: The user data submitted via a form, 
            containing the necessary information for user registration.
    Raises:\n
        CustomException: If user registration is disabled in the application settings.
    Returns:\n
        User: The newly registered user object.
    """
    check_rate_limit(request.client.host if request.client else "unknown", max_attempts=5, window_seconds=300)
    if settings.REGISTRATION_ENABLED == False:
        raise CustomException(status_code=403,
            detail="Registration is disabled",
        )
    new_user = await user_util.register_user(user_data, session)
    return new_user

