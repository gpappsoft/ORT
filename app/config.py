# Copyright (c) 2025 Marco Moenig (info@moenig.it)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT



from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    project_name: str = "ort"
    model_config = SettingsConfigDict(_env_file='.env', _env_file_encoding='utf-8')
    DATABASE_URI: str
    TOKEN_URL: str
    SQL_ECHO: bool = False
    CORS_ORIGINS: list[str] = []
    SECRET_KEY: str
    ALGORITHM: Literal["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: float | None = 60
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = False
    LOG_NAME: str = "ort.app_logs"
    LOG_ACCESS_NAME: str = "ort.access_logs"
    IMAGE_PATH: str
    REDIS_HOST: str | None = None
    REDIS_PORT: str | None = None
    REDIS_DB: str | None = None
    REDIS_USER: str | None = None
    REDIS_PASSWORD: str | None = None
    CACHE_TTL: int | None = 3600
    CACHE_MAXSIZE: int | None = 1000  
    CACHE_ENABLED: bool | None = True
    CACHE_TYPE: str | None = "local"
    EMAIL_CONFIRMATION: bool = False
    REGISTRATION_ENABLED: bool = True
    MAX_IMAGE_SIZE: int = 2097152  # 2 MB

settings = Settings(_env_file='.env', _env_file_encoding='utf-8')


