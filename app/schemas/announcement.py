from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Literal
from datetime import datetime
class CreateAnnouncementSchema(BaseModel):
    name: str = Field(min_length=3, max_length=100, detail='Название услуги')
    status: Literal['active']
    type: str = Field(max_length=100, detail='Тип услуги')
    description: str | None = Field(max_length=1000, detail='Описание услуги')
    price: int = Field(ge=0)
    duration_minutes: int = Field(ge=1, default=60)
    cancel_before_hours: int = Field(ge=1, default=24)
    

    @field_validator('description')
    @classmethod
    def description_validator(cls, value: str):
        if value == '':
            value = None
        return value

class AnnouncementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    name: str
    type: str
    description: str | None
    price: int
    status: str
    created_at: datetime
    updated_at: datetime

class AnnouncementResponseSchema(BaseModel):
    announcement: AnnouncementOut

class AnnouncementsResponseSchema(BaseModel):
    announcements: list[AnnouncementOut]
