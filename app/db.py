# Copyright (c) 2025 Marco Moenig (info@moenig.it)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

import sys

from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from loguru import logger

from app.config import settings
from app.lib.cache import cache


engine = create_async_engine(settings.DATABASE_URI, echo=settings.SQL_ECHO, future=True, pool_pre_ping=True)

async def init_db():
    
    try:
        async with engine.begin() as conn:
            await cache.clean_cache()
            #await conn.run_sync(SQLModel.metadata.drop_all)
            await conn.run_sync(SQLModel.metadata.create_all)
            logger.info("Database tables created")
    except Exception as e:
        logger.error(f"Shutting down application due to database connection failure: {e}")
        sys.exit(4)


async def get_session() -> AsyncSession: # type: ignore
    async_session =  sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        

