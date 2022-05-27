from datetime import datetime
from models import messages, database

async def insert_message(route_id: int, user_id: int, text: str, created: datetime, read: bool = False):
	msg = messages.insert().values(
            text=text,
            read=read,
            route_id=route_id,
            user_id=user_id,
            created=created
        )
	await database.execute(msg)
