# Copyright (c) 2025 Marco Moenig (info@moenig.it)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT


from fastapi import FastAPI
from sqlmodel.ext.asyncio.session import AsyncSession
from contextlib import asynccontextmanager
from app.exceptions import CustomExceptionMiddleware
from app.config import settings
from app.db import init_db
from app.routers import users,auth,tracks,images
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan, title=settings.project_name, docs_url="/api/docs")

app.add_middleware(CustomExceptionMiddleware)
_cors_origins = settings.CORS_ORIGINS
_allow_credentials = bool(_cors_origins) and "*" not in _cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(users.router)
app.include_router(tracks.router)
app.include_router(auth.router)
app.include_router(images.router)
