import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_env_path = os.path.join(_backend_dir, "env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)
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
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_TEMPLATE_NAME: str = "hello_world"
    FAST2SMS_API_KEY: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    class Config:
        env_file = (_env_path, "env", ".env", "backend/env")
        extra = "ignore"

settings = Settings()

