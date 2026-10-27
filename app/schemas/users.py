from pydantic import BaseModel
from datetime import datetime
from typing import Literal
#TODO добавить в таблицу пользователя конфигурации например как разрешить паказывать почту или нет

class AccountData(BaseModel):
    id: int
    username: str
    email: str | Literal['Недоступен к просмотру']
    created_at: datetime

class AcountSettingsData(BaseModel):
    two_factor_enabled: bool 
    show_email: bool

class AccountDataResponseSchema(BaseModel):
    user: AccountData

class MyAccountDataResponseSchema(BaseModel):
    user: AccountData
    settings: AcountSettingsData