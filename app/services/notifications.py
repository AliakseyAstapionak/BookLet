from sqlalchemy.ext.asyncio import AsyncSession
from models import NotificationModel
from sqlalchemy import select


class NotificationService:

    @staticmethod
    async def send_book_message(to_user_id: int, sender_id: int,title: str, msg_text: str, db: AsyncSession):
        message = NotificationModel(to_user_id=to_user_id, sender_id=sender_id, title=title, text=msg_text)
        db.add(message)
        await db.commit()
        return True
    
#TODO подумать как сделать так чтобы выводило и имя пользователя
    @staticmethod
    async def get_my_notifications(user_id: int, db: AsyncSession):
        query = (select(NotificationModel).where(NotificationModel.to_user_id == user_id).order_by(NotificationModel.created_at.desc()))
        result = await db.execute(query)
        return result.scalars().all()