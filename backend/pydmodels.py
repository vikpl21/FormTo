import datetime
from typing import Optional

from pydantic import BaseModel, validator


class Phone(BaseModel):
    phone: int


class PhoneAndCode(Phone):
    code: str


class Register(BaseModel):
    name: str
    email: str
    phone: str
    password: str


class CreateRoute(BaseModel):
    name: str
    date: datetime.date
    time: datetime.time
    description: str
    vehicle: Optional[str] = None
    seats: Optional[int] = None
    price: Optional[str] = None

    @validator("date")
    def check_date(cls, v):
        now = datetime.datetime.now().date()
        if v < now:
            raise ValueError("old datetime")
        return v

    @validator("name")
    def check_name(cls, v):
        if any([char in v for char in "<>%$/\\\[\]|\+\_\(\)=!@#&?:;\'\"])"]):
            raise ValueError("Лише букви")
        return v

    @validator("description")
    def check_description(cls, v):
        if any([char in v for char in "\<\>\$\/\\\\[\]\|\+\_\=\#\&\%\^\*"]):
            raise ValueError("description")
        return v

    @validator("vehicle")
    def check_vehicle(cls, v):
        if any([char in v for char in "\<\>\$\/\\\\[\]\|\+\_\=\#\&\%\^\*"]):
            raise ValueError("vehicle")
        return v
    
    @validator("price")
    def check_price(cls, v):
        if any([char in v for char in "<>%$/\\\[\]|\+_\(\)=!@#&?:;\'\"])"]):
            raise ValueError("price")
        return v


class Search(BaseModel):
    route: str
    datetime: datetime.date
    seats: int
    driver: bool

    @validator("datetime")
    def check_date(cls, v):
        now = datetime.datetime.now().date()
        if v < now:
            raise ValueError("old datetime")
        return v


class User(BaseModel):
    name: str
    email: str
    password: str
    token: Optional[str] = None


class SetPassengers(BaseModel):
    seats: int
    description: str
    router: str
    name: str
    owner_id: Optional[int] = None
    datetime: str


class Route(BaseModel):
    id: str
    name: Optional[str] = None
    datetime: Optional[str] = None


class UpdateRoute(Route):
    seats: int
    desc: Optional[str] = None

    @validator("desc")
    def check_desc(cls, v):
        if any([char in v for char in "<>%$/\\\[\]|\+\-_\(\)=!@#&?:;\'\"])"]):
            raise ValueError("Заборонені символи")
        return v


class DeleteRoute(BaseModel):
    pass_id: int
    user_id: int
    datetime: str
    route_name: str
    route_id: str


class RemovePassenger(BaseModel):
    user_id: int
    pass_id: int
    route_id: str


class PassengerData(BaseModel):
    route_id: str
    user_id: int
