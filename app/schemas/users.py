from pydantic import BaseModel
from datetime import datetime
#TODO добавить в таблицу пользователя конфигурации например как разрешить паказывать почту или нет

class AccountData(BaseModel):
    id: int
    username: str
    email: str | None
    created_at: datetime

class AccountDataResponseSchema(BaseModel):
    user: AccountData