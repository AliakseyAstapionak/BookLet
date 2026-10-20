from pydantic import BaseModel, Field, field_validator
from enum import Enum
from typing import Optional
from enum import Enum
from typing import Optional
from pydantic import BaseModel, model_validator

#TODO обьеденить эти схемы потом с my_anc

class SortEnum(str, Enum):
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    NAME = "name"

class AnnouncementFiltersSchema(BaseModel):
    provider: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    limit: int = Field(ge=1, le=150, default=20)
    offset: int = Field(ge=0, default=0)
    sort: SortEnum = SortEnum.NEWEST

    @model_validator(mode='after')
    def validate_price(self) -> 'AnnouncementFiltersSchema':
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError('Максимальная цена не может быть меньше минимальной')
        return self