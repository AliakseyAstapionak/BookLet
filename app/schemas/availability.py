from pydantic import BaseModel, Field
from datetime import time
from pydantic import BaseModel, Field, model_validator


class CreateAvailabilityRuleSchema(BaseModel):
    weekday: int = Field(ge=0, le=6, description='0 = понедельник ... 6 = воскресенье')
    start_time: time
    end_time: time

    @model_validator(mode='after')
    def check_order(self):
        if self.end_time <= self.start_time:
            raise ValueError('Конец окна должен быть позже начала')
        return self