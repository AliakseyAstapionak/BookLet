from pydantic import BaseModel, Field
from typing import Literal

class CreateAnnouncementSchema(BaseModel):
    name: str = Field(min_length=3, max_length=100, detail='Название услуги')
    status: Literal['active', 'archived', 'booked']
    type: str = Field(max_length=100, detail='Тип услуги')
    description: str | None = Field(max_length=1000, detail='Описание услуги')
    price: int = Field(ge=0)

