import datetime
import re

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.sql import func

from auth import (confirm_token, create_access_token, get_current_user,
                  get_current_user_route)
from func import insert_message
from gtranslate import translate_text
from models import database, messages, offers, passengers, routes, users
from pydmodels import (CreateRoute, DeleteRoute, PassengerData, Register,
                       RemovePassenger, Route, Search, SetPassengers,
                       UpdateRoute, User)
from settings import Settings, timezone
from webs import manager, ws

api = FastAPI(docs_url=None, redoc_url=None)
api.include_router(ws)

settings = Settings()

mail_config = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_username,
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_TLS=True,
    MAIL_SSL=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER="./templates",
)

hash = CryptContext(schemes=["bcrypt"], deprecated="auto")

origins = ["*"]

api.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.on_event("startup")
async def startup():
    await database.connect()


@api.on_event("shutdown")
async def shutdown():
    await database.disconnect()


@api.get("/")
async def main():
    return {"message": "FromTo"}


@api.get("/user")
async def user(current_user: User = Depends(get_current_user)):
    return current_user


async def create_users():
    await database.execute(
        users.insert().values(
            name="Danil",
            email="danil@mail.com",
            phone="+380991273991",
            password=hash.hash("danil"),
            is_active=True,
        )
    )
    await database.execute(
        users.insert().values(
            name="Lena",
            email="lena@mail.com",
            phone="+380994473991",
            password=hash.hash("lena"),
            is_active=True,
        )
    )


@api.post("/register")
async def register(user: Register):
    # await create_users()

    user_in_db = await database.fetch_one(
        users.select().where(users.c.email == user.email)
    )
    if user_in_db:
        raise HTTPException(status_code=400, detail="Користувач вже зареєстрований")
    user_id = await database.execute(
        users.insert().values(
            name=user.name,
            email=user.email,
            phone="+"+user.phone,
            password=hash.hash(user.password),
            is_active=False,
        )
    )
    token = create_access_token({"id": user_id, "sub": user.email})

    message = MessageSchema(
        subject="Лист підтвредження від FromTo",
        recipients=[user.email],
        template_body={
            "user_email": user.email,
            "confirm_email": settings.app_url + "/#/confirm-email/" + token
        }
    )
    fm = FastMail(mail_config)
    await fm.send_message(
        message,
        template_name="email_template.html"
    )
    return {"message": "Підтвердіть свою пошту"}


@api.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await database.fetch_one(
            users.select().where(users.c.email == form_data.username)
        )
    if user:
        user = dict(user)
    if not user or not hash.verify(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Невірна пошта або пароль"
        )
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="Підтвердіть свою пошту"
        )
    access_token = create_access_token(data={"id": user["id"], "sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer", "message": "Вхід виконано", "name": user["name"], "rating_user": user["rating_user"]}


@api.post("/create-route")
async def create_route(route: CreateRoute, current_user: User = Depends(get_current_user)):
    import uuid
    translate_route = translate_text("uk", route.name.lower().title())
    date_and_time = datetime.datetime.combine(route.date, route.time)
    query = select(routes.c.id).where(and_(
            routes.c.user_id == current_user["id"],
            routes.c.status != 1,
            routes.c.datetime >= timezone()
    ))
    result = await database.fetch_one(query)
    if result:
        raise HTTPException(401, detail="У вас вже є дійсний маршрут")
    await database.execute(
        routes.insert().values(
            id=str(uuid.uuid4()),
            route=translate_route["translatedText"],
            datetime=date_and_time,
            description=route.description,
            car=route.vehicle,
            seats=route.seats,
            price=route.price,
            status=0,
            user_id=current_user["id"]
        )
    )
    return {"message": "Маршрут створено"}


@api.post("/search")
async def search(search: Search):
    if search.datetime > timezone().date():
        timef_to_time = datetime.datetime.strptime("00:00:00", "00:00:00").time()
    else:
        time = timezone().strftime("%H:%M:00")
        timef_to_time = datetime.datetime.strptime(time, "%H:%M:00").time()
    date = datetime.datetime.combine(search.datetime, timef_to_time)
    
    # text = translate_text("uk", search.route.title())

    # cities = re.split(r"[.|,|-| ]", text["translatedText"].lower().title().replace(", ", ","))
    cities = re.split(r"[.|,|-| ]", search.route.lower().title())
    cities_inline = "%".join(cities).replace(" ", "")

    if search.driver:
        is_driver = routes.c.car == ""
    else:
        is_driver = routes.c.car != ""
        
    query = select(routes, users.c.name, users.c.rating_user)\
        .select_from(routes.join(users))\
        .where(and_(
            routes.c.route.like(f"%{cities_inline}%"),
            routes.c.seats >= search.seats,
            routes.c.status == 0,
            routes.c.datetime >= date,
            is_driver
    ))
    result = await database.fetch_all(query)
    return result


@api.get("/route/{id}")
async def route(id: str):
    sum = select(func.sum(passengers.c.seats)).where(and_(passengers.c.route_id == id, passengers.c.description.like('')))
    query = select(routes, users.c.name, users.c.rating_user).select_from(routes.join(users)).where(routes.c.id == id)
    query_result = await database.fetch_one(query)
    result_sum = await database.fetch_val(sum)
    if query_result is not None:
        query_result = dict(query_result)
        query_result.update({"sum": result_sum})
    return query_result


@api.post("/set-passengers")
async def set_passengers(route: SetPassengers, current_user: User = Depends(get_current_user)):
    date = datetime.datetime.today()
    query = select(passengers.c.id).select_from(passengers.join(routes)).where(
        and_(passengers.c.user_id == current_user["id"], routes.c.datetime > date, passengers.c.description == '')
    )
    result = await database.fetch_one(query)
    if result:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="У вас вже є заброньоване місце"
        )
    await database.execute(
        passengers.insert().values(
            route_id=route.router,
            user_id=current_user["id"],
            seats=route.seats,
            description=route.description,
        )
    )
    p_phone = current_user["phone"]
    p_name = current_user["name"]
    msg = messages.insert().values(
        read=False,
        route_id=route.router,
        user_id=route.owner_id,
        text=f"Пасажир {p_name}, {p_phone} долучився до маршруту '{route.name}' {route.datetime}.",
        created=datetime.datetime.strptime(datetime.datetime.strftime(timezone(), "%d.%m.%y %H:%M"), "%d.%m.%y %H:%M")
    )
    await database.execute(msg)
    return {"message": "Ви долучились до маршруту"}


@api.get("/my-seats")
async def user_routes(current_user: User = Depends(get_current_user)):
    query = select(routes, passengers.c.id.label("p_id"), passengers.c.seats.label("booking_seats"),
                users.c.id, users.c.name, users.c.phone)\
                    .select_from(routes.join(passengers).join(users))\
                        .where(and_(
                            passengers.c.user_id == current_user["id"],
                            routes.c.datetime >= timezone(),
                            routes.c.status == 0,
                            passengers.c.description.like("")
                        )).order_by(desc(routes.c.datetime))
    result = await database.fetch_one(query)
    if result is not None:
        result = dict(result)
        return result
    return {}


@api.get("/my-routes")
async def driver_routes(current_user: User = Depends(get_current_user), current_user_route: User = Depends(get_current_user_route)):
    query_seats = select(func.sum(passengers.c.seats)).where(and_(
        passengers.c.route_id == current_user_route["id"],
        passengers.c.description.like("")
    ))
    query = select(routes.c.id, routes.c.route, routes.c.car, routes.c.seats, routes.c.datetime, routes.c.description).where(and_(
        routes.c.user_id == current_user["id"],
        routes.c.datetime >= timezone(),
        routes.c.status == 0
    ))
    seats = await database.fetch_val(query_seats)
    route = await database.fetch_one(query)
    if route is not None:
        route = dict(route)
        route.update({"sum": seats})
        return route
    return {}


@api.get("/routes-history")
async def routes_history(current_user: User = Depends(get_current_user)):
    query = select(routes)\
                        .where(and_(
                            routes.c.user_id == current_user["id"],
                            or_(
                                routes.c.datetime < timezone(),
                                routes.c.status == 1
                            )
                        )).order_by(desc(routes.c.datetime))
    result = await database.fetch_all(query)
    return result


@api.get("/user-routes-history")
async def user_routes_history(current_user: User = Depends(get_current_user)):
    query = select(routes, passengers.c.description.label("p_desc"), passengers.c.seats, users.c.id,
        users.c.name, users.c.phone, passengers.c.rating, passengers.c.comment).select_from(routes.join(passengers).join(users)).where(
                and_(
                    passengers.c.user_id == current_user["id"],
                    or_(
                        routes.c.datetime < timezone(),
                        routes.c.status == 1,
                        passengers.c.description != ""
                    )
                )).order_by(desc(routes.c.datetime))
    result = await database.fetch_all(query)
    return result


@api.post("/delete-route")
async def delete_route(route: DeleteRoute, current_user: User = Depends(get_current_user)):
    await database.execute(
        passengers.update().where(passengers.c.id == route.pass_id).values(description="Ви відмінили бронь")
    )
    p_name = current_user["name"]
    p_phone = current_user["phone"]
    text_msg = f"Пасажир {p_name}, {p_phone} відмінив бронювання '{route.route_name}', {route.datetime}"
    created_msg = datetime.datetime.strptime(datetime.datetime.strftime(timezone(), "%d.%m.%y %H:%M"), "%d.%m.%y %H:%M")

    await insert_message(route.route_id, route.user_id, text_msg, created_msg)
    return {"message": "Маршрут видалено"}


@api.post("/get-route")
async def get_route(route: Route):
    return await database.fetch_one(
        select(passengers.c.id, routes.c.seats, func.sum(passengers.c.seats).label("my_seats")).select_from(
            routes.join(passengers))\
            .where(routes.c.id == route.id)\
                .group_by(passengers.c.id, routes.c.seats)
    )


@api.post("/update-route")
async def update_route(data: UpdateRoute, current_user: User = Depends(get_current_user)):
    query = f"""
        UPDATE passengers SET seats = {data.seats}
        WHERE id = {data.id}
    """
    await database.execute(query)
    return {"message": "Маршрут змінено"}


@api.get("/check-active-route")
async def check_active_route(current_user: User = Depends(get_current_user)):
    query = select(routes.c.id).where(
        and_(
            routes.c.user_id == current_user["id"],
            routes.c.status != 1,
            routes.c.datetime >= timezone()
        )
    )
    result = await database.fetch_val(query)
    if result:
        return {"message": "У вас вже є дійсний маршрут"}


@api.post("/change-active-route")
async def change_active_route(route: Route, current_user: User = Depends(get_current_user)):
    query = routes.update().where(routes.c.id == route.id).values(status=1)
    await database.execute(query)
    ids = select(passengers.c.user_id).where(and_(
        passengers.c.route_id == route.id,
        passengers.c.description.like('')
    ))
    result_ids = await database.fetch_all(ids)
    query = passengers.update().where(and_(
                passengers.c.route_id == route.id,
                passengers.c.description.like("")
            )).values(description="Водій відмінив маршрут")
    await database.execute(query)

    text_msg = f"Водій відмінив маршрут '{route.name}', {route.datetime}"
    created_msg = datetime.datetime.strptime(datetime.datetime.strftime(timezone(), "%d.%m.%y %H:%M"), "%d.%m.%y %H:%M")
    for i in result_ids:
        await insert_message(route.id, dict(i).get("user_id"), text_msg, created_msg)
    await manager.send_number_of_message_all_users_by_route(result_ids)
    return {"message": "Ви відмінили маршрут"}


@api.get("/get-confirm-email/{token}")
async def get_confirm_email(token: str):
    check_user = await confirm_token(token)
    if check_user:
        query = users.update()\
            .where(users.c.email == check_user)\
            .values(is_active=True)
        await database.execute(query)
        return {"message": "Ви підтвердили пошту"}


@api.get("/route/{id}/passengers")
async def route_passengers(id: str, current_user: User = Depends(get_current_user)):
    query = (
        select(routes.c.datetime, passengers.c.id, passengers.c.route_id, passengers.c.seats, passengers.c.description, users.c.id.label("user_id"), users.c.name, users.c.email, users.c.phone)\
            .select_from(routes.join(passengers).join(users))\
                .where(and_(passengers.c.route_id == id, passengers.c.description == ''))
    )
    result = await database.fetch_all(query)
    if not result:
        query = select(passengers.c.id, passengers.c.route_id, passengers.c.seats, users.c.id.label("user_id"), passengers.c.description, users.c.name, users.c.email, users.c.phone)\
                        .select_from(passengers.join(users))\
                            .where(and_(passengers.c.route_id == id))
        result = await database.fetch_all(query)
    print(query)
    return result


@api.get("/users/{id}")
async def get_user(id: int, current_user: User = Depends(get_current_user)):
    query = (
        select(users.c.name, users.c.email)\
            .where(users.c.id == id)
    )
    result = await database.fetch_one(query)
    return result


@api.post("/route/remove-passenger")
async def remove_passenger(data: RemovePassenger, current_user: User = Depends(get_current_user)):
    query = passengers.update().where(passengers.c.id == data.pass_id).values(description="Водій вилучив вас з маршруту")
    await database.execute(query)
    query_route = routes.select().where(routes.c.id == data.route_id)
    route = dict(await database.fetch_one(query_route))
    
    route_name = route["route"]
    route_datetime = route["datetime"]
    route_datetime_format = datetime.datetime.strftime(route_datetime, "%d.%m.%y %H:%M")
    text_msg = f"Водій вилучив вас з маршруту '{route_name}' на {route_datetime_format}."
    created_msg = datetime.datetime.strptime(datetime.datetime.strftime(timezone(), "%d.%m.%y %H:%M"), "%d.%m.%y %H:%M")
    
    await insert_message(data.route_id, data.user_id, text_msg, created_msg)
    return {"message": "Ви вилучили пасажира, йому прийде повідомлення"}


@api.get("/number-messages")
async def number_message(current_user: User = Depends(get_current_user)):
    query = select(func.count(messages.c.id)).where(and_(
        messages.c.user_id == current_user["id"],
        messages.c.read == False
    ))
    number_messages = await database.fetch_val(query)
    return number_messages


@api.get("/messages-history")
async def messages_history(current_user: User = Depends(get_current_user)):
    query = select(messages).where(and_(
        messages.c.user_id == current_user["id"],
        messages.c.read == True
    )).order_by(desc(messages.c.created))
    return await database.fetch_all(query)


@api.get("/get-message")
async def get_message(current_user: User = Depends(get_current_user)):
    query = select(messages).where(and_(
        messages.c.user_id == current_user["id"],
        messages.c.read == False
    ))
    result = await database.fetch_all(query)
    return result


@api.patch("/change-read-message")
async def change_read_message(current_user: User = Depends(get_current_user)):
    query = messages.update().where(and_(
        messages.c.user_id == current_user["id"],
        messages.c.read == False
    )).values(read=True)
    await database.execute(query)
    return {"message": "OK"}


@api.post("/offer")
async def offer(data: PassengerData, current_user_route: User = Depends(get_current_user_route)):
    query = select(routes).where(
        routes.c.id == current_user_route["id"]
    )
    result = await database.fetch_val(query)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="У вас немає маршруту"
        )
    query = select(offers).where(
        and_(
            offers.c.route_d_id == current_user_route["id"],
            offers.c.route_p_id == data.route_id
        )
    )
    result = await database.fetch_val(query)
    if result:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="Пропозиція вже відправлена"
        )
    query = offers.insert().values(
        route_p_id=data.route_id,
        route_d_id=current_user_route["id"],
        user_id=data.user_id,
        description="Вам запропонували маршрут",
    )
    await database.execute(query)
    
    route_name = current_user_route["route"]
    route_datetime = current_user_route["datetime"]
    route_datetime_format = datetime.datetime.strftime(route_datetime, "%d.%m.%y %H:%M")
    text_msg = f"Вам відправлена пропозиція маршруту '{route_name}' на {route_datetime_format}."
    created_msg = datetime.datetime.strptime(datetime.datetime.strftime(timezone(), "%d.%m.%y %H:%M"), "%d.%m.%y %H:%M")

    await insert_message(current_user_route["id"], data.user_id, text_msg, created_msg)
    await manager.send_number_messages_by_user(data.user_id)
    return {"message": "Пропозиція відправлена"}


@api.get("/offers/{id}")
async def get_offers(id: str, current_user: User = Depends(get_current_user)):
    query = select(offers.c.id.label("offer"), routes.c.route, routes.c.id, routes.c.seats, routes.c.datetime, routes.c.status)\
        .select_from(offers.join(routes)).where(
        and_(
            offers.c.route_p_id == id,
            offers.c.user_id == current_user["id"],
        )
    )
    result = await database.fetch_all(query)
    return result


@api.post("/update-seats")
async def update_seats(route: UpdateRoute, current_user: User = Depends(get_current_user)):
    query = select(func.sum(passengers.c.seats)).where(and_(
        passengers.c.route_id == route.id,
        passengers.c.description.like("")
    ))
    sum_free_seats = await database.fetch_val(query)
    if not sum_free_seats: sum_free_seats = 0
    new_route_seats = routes.update().where(routes.c.id == route.id).values(seats=sum_free_seats + route.seats, description=route.desc)
    await database.execute(new_route_seats)
    return {"message": "Дані оновлено"}


class SupportData(BaseModel):
    name: str
    email: EmailStr
    message: str


# @api.post("/support-message")
# async def support_message(data: SupportData):
#     message = MessageSchema(
#         subject=f"Зворотній зв'язок від {data.name}",
#         recipients=[data.email],
#         template_body={
#             "message": data.message,
#         }
#     )
#     fm = FastMail(mail_config)
#     await fm.send_message(
#         message,
#         template_name="support_template.html"
#     )
#     return {"message": "Лист відправлено"}


class Rating(BaseModel):
    routeId: str
    driverId: str
    rating: str
    comment: str


@api.post("/route/rating")
async def rating_route(data: Rating, current_user: User = Depends(get_current_user)):
    print(data)
    rating_insert = passengers.update().where(and_(
        passengers.c.route_id == data.routeId,
        passengers.c.user_id == current_user["id"]
    )).values(
        rating=float(data.rating),
        comment=data.comment,
    )
    await database.execute(rating_insert)

    # Рейтинг маршруту
    all_rating_route = select((func.sum(passengers.c.rating)/func.count(passengers.c.rating))).where(
        and_(
            passengers.c.route_id == data.routeId,

        )
    )
    avg_rating_route = await database.fetch_val(all_rating_route)

    rating_insert_route = routes.update().where(routes.c.id == data.routeId).values(rating_route=avg_rating_route)
    await database.execute(rating_insert_route)

    # Рейтинг користувача
    all_rating_user = select((func.sum(routes.c.rating_route)/func.count(routes.c.rating_route))).where(
        and_(
            routes.c.user_id == int(data.driverId),
            routes.c.car != ""
        )
    )
    avg_rating_user = await database.fetch_val(all_rating_user)

    update_user_rating = users.update().where(users.c.id == int(data.driverId)).values(rating_user=avg_rating_user)
    await database.execute(update_user_rating)
    return {"message": "Оцінено"}
