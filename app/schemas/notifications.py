from pydantic import BaseModel
from typing import List
from datetime import datetime
class NotificationSchema(BaseModel): 
    id: int   
    sender_id: int | None
    type: str
    title: str        
    text: str
    created_at: datetime

class NotificationResponseSchema(BaseModel):
    notification: NotificationSchema

class MyNotificationsResponseSchema(BaseModel):
    notifications: List[NotificationSchema]

class NotificationDataSchema(NotificationResponseSchema):
    pass

