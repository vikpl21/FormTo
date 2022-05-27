from email.policy import default
from psycopg2 import Date
from sqlalchemy import (
    Boolean,
    String,
    Integer,
    Table,
    ForeignKey,
    Column,
    DateTime,
    MetaData,
    Float,
    create_engine,
)
from sqlalchemy.dialects.postgresql import UUID
import databases

from settings import Settings

settings = Settings()
database = databases.Database(settings.database_url)
metadata = MetaData()
engine = create_engine(settings.database_url)

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(20)),
    Column("phone", String(20), nullable=False),
    Column("email", String(120), unique=True),
    Column("password", String(255)),
    Column("rating_user", Float, default=0),
    Column("is_active", Boolean),
)

routes = Table(
    "routes",
    metadata,
    Column("id", String(100), primary_key=True),
    Column("route", String(255)),
    Column("datetime", DateTime),
    Column("price", String(20)),
    Column("description", String(255)),
    Column("car", String(25)),
    Column("seats", Integer),
    Column("status", Integer, default=0),
    Column("rating_route", Float, default=0),
    Column("user_id", ForeignKey("users.id"))
)

passengers = Table(
    "passengers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("route_id", ForeignKey("routes.id")),
    Column("user_id", ForeignKey("users.id")),
    Column("seats", Integer),
    Column("description", String(255)),
    Column("rating", Float),
    Column("comment", String(255)),
)

messages = Table(
    "messages",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("text", String(120), nullable=False),
    Column("read", Boolean, default=False),
    Column("created", DateTime),
    Column("route_id", ForeignKey("routes.id")),
    Column("user_id", ForeignKey("users.id"))
)

offers = Table(
    "offers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("route_p_id", String(100)),
    Column("route_d_id", ForeignKey("routes.id")),
    Column("user_id", ForeignKey("users.id")),
    Column("description", String)
)

metadata.create_all(engine)
