from datetime import time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateAvailabilityRuleSchema(BaseModel):
    weekday: int = Field(ge=0, le=6, description='0 = понедельник ... 6 = воскресенье')
    start_time: time
    end_time: time

    @model_validator(mode='after')
    def check_order(self):
        if self.end_time <= self.start_time:
            raise ValueError('Конец окна должен быть позже начала')
        return self


class AvailabilityRuleOutSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    weekday: int
    start_time: time
    end_time: time


class AvailabilityResponseSchema(BaseModel):
    rules: list[AvailabilityRuleOutSchema]


class AvailabilityRuleResponseSchema(BaseModel):
    success: bool = True
    msg: str
    rule: AvailabilityRuleOutSchema