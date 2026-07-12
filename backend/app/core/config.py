import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    ALPACA_API_KEY: str
    ALPACA_SECRET_KEY: str
    TELEGRAM_BOT_TOKEN: str
    FIREBASE_PROJECT_ID: str
    FIREBASE_CHECKER_URL: str
    EXPO_ACCESS_TOKEN: str

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        extra="ignore"
    )

settings = Settings()