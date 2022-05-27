import os
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy import and_, func, select

from auth import ALGORITHM
from models import database, messages, passengers

ws = APIRouter()


async def get_number_of_messages_by_user(user_id: int):
    count = select(func.count(messages.c.id)).where(and_(
        messages.c.user_id == user_id,
        messages.c.read == False
    ))
    return await database.fetch_val(count)


async def get_passengers_by_route(route_id: int):
    psgs = select(passengers.c.user_id).where(and_(
        passengers.c.route_id == route_id,
        passengers.c.description.like("")
    ))
    return await database.fetch_all(psgs)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[WebSocket] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[f"client_id_{client_id}"] = websocket
        nom = await get_number_of_messages_by_user(client_id)
        await websocket.send_text(str(nom))

    async def disconnect(self, client_id: int):
        del self.active_connections[f"client_id_{client_id}"]

    async def send_personal_message(self, client_id: int, message: str):
        try:
            ws = self.active_connections[f"client_id_{client_id}"]
        except KeyError:
            print(f"User #{client_id} not found")
        await ws.send_text(message)
    
    async def send_number_messages_by_user(self, client_id: int):
        try:
            ws = self.active_connections[f"client_id_{client_id}"]
            count = await get_number_of_messages_by_user(client_id)
            await ws.send_text(str(count))
        except KeyError:
            print(f"User #{client_id} not found")
    
    async def send_number_of_message_all_users_by_route(self, psgs: list):
        for s in psgs:
            user_id = dict(s).get("user_id")
            for k, v in self.active_connections.items():
                if k == f"client_id_{user_id}":
                    nom = await get_number_of_messages_by_user(int(user_id))
                    await v.send_text(str(nom))


manager = ConnectionManager()


@ws.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        payload = jwt.decode(token, os.environ["SECRET_KEY"], algorithms=[ALGORITHM])
        client_id: int = payload.get("id")
    except JWTError:
        print("JWTError")
    await manager.connect(websocket, client_id)
    print(manager.active_connections)
    try:
        while True:
            data = await websocket.receive_json()
            type = data["type"]
            if type == "get_number":
                reciever_id = int(data["id"])
                await manager.send_number_messages_by_user(reciever_id)
            elif type == "read_messages":
                nom = await get_number_of_messages_by_user(client_id)
                await websocket.send_text(str(nom))
            else:
                print("Case not found")
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
