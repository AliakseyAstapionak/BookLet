from pydantic import BaseModel, Field, field_validator
from typing import Literal

class CreateAnnouncementSchema(BaseModel):
    name: str = Field(min_length=3, max_length=100, detail='Название услуги')
    status: Literal['active', 'archived', 'booked']
    type: str = Field(max_length=100, detail='Тип услуги')
    description: str | None = Field(max_length=1000, detail='Описание услуги')
    price: int = Field(ge=0)

    @field_validator('description')
    @classmethod
    def description_validator(cls, value: str):
        if value == '':
            value = None
        return value

