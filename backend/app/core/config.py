from dotenv import load_dotenv
from pydantic_settings import BaseSettings
load_dotenv()
load_dotenv("env")
load_dotenv("backend/env")

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    JWT_SECRET: str = "supersecretjwtkeyforrideshieldhackathonsprint2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    class Config:
        env_file = ("env", ".env", "backend/env")
        extra = "ignore"

settings = Settings()

