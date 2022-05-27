import os
from datetime import datetime, timedelta

from pydantic import BaseSettings

def timezone():
    return datetime.now() + timedelta(hours=3)

class Settings(BaseSettings):
    # account_sid: str
    # auth_token: str
    # service_sid: str
    # app_url: str = os.environ["APP_URL"]
    # database_url: str = os.environ["DATABASE_URL"]
    # mail_username: str = os.environ["MAIL_USERNAME"]
    # mail_password: str = os.environ["MAIL_PASSWORD"]
    # mail_from: str = os.environ["MAIL_FROM"]
    # secret_key: str = os.environ["SECRET_KEY"]
    # algorithm: str = os.environ["ALGORITHM"]
    # access_token_expire_minutes: int = os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"]

    app_url: str
    database_url: str
    mail_username: str
    mail_password: str
    mail_from: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    class Config:
        env_file = ".env"
