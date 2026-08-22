import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    JWT_SECRET: str = "supersecretjwtkeyforrideshieldhackathonsprint2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
