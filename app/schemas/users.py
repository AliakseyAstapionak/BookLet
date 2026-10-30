from pydantic import BaseModel
from datetime import datetime
from typing import Literal

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