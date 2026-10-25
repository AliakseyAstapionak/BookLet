from pydantic import BaseModel
from typing import List
from datetime import datetime
class NotificationResponseSchema(BaseModel):    
    sender_id: int
    title: str        
    text: str
    created_at: datetime

class MyNotificationsResponseSchema(BaseModel):
    notifications: List[NotificationResponseSchema]