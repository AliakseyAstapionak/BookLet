from sqlalchemy.ext.asyncio import AsyncSession
from models import NotificationModel
from sqlalchemy import select, or_
from schemas import NotificationDataSchema

class NotificationService:

    @staticmethod
    async def send_book_message(to_user_id: int, sender_id: int,title: str, msg_text: str, db: AsyncSession):
        message = NotificationModel(to_user_id=to_user_id, sender_id=sender_id, title=title, text=msg_text)
        db.add(message)
        await db.commit()
        return True
    
#TODO подумать как сделать так чтобы выводило и имя пользователя(вообще оно и не надо потому что в тексте сообщений есть имя от кого отпралено)

    @staticmethod
    async def get_my_all_notifications(user_id: int, db: AsyncSession):
        query = (select(NotificationModel).where(or_(NotificationModel.to_user_id == user_id, NotificationModel.sender_id == user_id)).order_by(NotificationModel.created_at.desc()))
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_my_encoming_notifications(user_id: int, db: AsyncSession):
        query = (select(NotificationModel).where(NotificationModel.to_user_id == user_id).order_by(NotificationModel.created_at.desc()))
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_my_sent_notifications(user_id: int, db: AsyncSession):
        query = (select(NotificationModel).where(NotificationModel.sender_id == user_id).order_by(NotificationModel.created_at.desc()))
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_my_incoming_notification(not_id: int, client_id: int, db: AsyncSession) -> NotificationDataSchema:
        query = (select(NotificationModel).where(NotificationModel.id == not_id, NotificationModel.to_user_id == client_id))
        result = await db.execute(query)
        return result.scalar()

    @staticmethod
    async def get_my_sent_notification(not_id: int, client_id: int, db: AsyncSession) -> NotificationDataSchema:
        query = (select(NotificationModel).where(NotificationModel.id == not_id, NotificationModel.sender_id == client_id))
        result = await db.execute(query)
        return result.scalar()