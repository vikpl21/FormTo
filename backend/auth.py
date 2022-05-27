import os
import datetime

from fastapi import HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import and_

from jose import jwt, JWTError
from models import database, users, routes
from settings import timezone

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(hours=3) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, os.environ["SECRET_KEY"], algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Для цього необхідно увійти або зареєструватися",
        headers={"WWW-Authenticate": "Bearer"},
    )
    return await verify_token(token, credentials_exception)


async def verify_token(token: str, credentials_exception: str):
    try:
        payload = jwt.decode(token, os.environ["SECRET_KEY"], algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        id: int = payload.get("id")
        user = await database.fetch_one(users.select().where(users.c.id == id))
        if username is None:
            raise credentials_exception
        return user
    except JWTError:
        raise credentials_exception


async def get_route(token: str, credentials_exception: str):
    try:
        payload = jwt.decode(token, os.environ["SECRET_KEY"], algorithms=[ALGORITHM])
        id: int = payload.get("id")
        query = routes.select().where(and_(
            routes.c.user_id == id,
            routes.c.datetime >= timezone(),
            routes.c.status == 0
        ))
        route = await database.fetch_one(query)
        if route is not None:
            route = dict(route)
            return route
        return {"id": None}
    except JWTError:
        raise credentials_exception


async def get_current_user_route(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Для цього необхідно увійти",
        headers={"WWW-Authenticate": "Bearer"},
    )
    return await get_route(token, credentials_exception)


async def confirm_token(token: str):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Посилання не дійсне",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, os.environ["SECRET_KEY"], algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = dict(await database.fetch_one(
            users.select().where(and_(users.c.email == email))
    ))
    if user is None:
        raise credentials_exception
    if user["is_active"]:
        raise credentials_exception
    return user["email"]
