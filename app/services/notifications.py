from sqlalchemy.ext.asyncio import AsyncSession
from models import NotificationModel
from sqlalchemy import select, or_, func, update
from schemas import NotificationDataSchema

class NotificationService:

    @staticmethod
    async def send_book_message(to_user_id: int, sender_id: int, title: str, msg_text: str, db: AsyncSession,
                                notif_type: str = 'general', booking_id: int | None = None, commit: bool = True):
        message = NotificationModel(to_user_id=to_user_id, sender_id=sender_id, title=title, text=msg_text,
                                    type=notif_type, booking_id=booking_id)
        db.add(message)
        if commit:
            await db.commit()
        return True
    

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

    @staticmethod
    async def get_unread_count(user_id: int, db: AsyncSession) -> int:
        query = (select(func.count()).select_from(NotificationModel)
                 .where(NotificationModel.to_user_id == user_id, NotificationModel.is_read.is_(False)))
        return (await db.execute(query)).scalar_one()

    @staticmethod
    async def mark_read(not_id: int, user_id: int, db: AsyncSession) -> bool:
        """False, если такого входящего уведомления нет. Повторный вызов безопасен."""
        result = await db.execute(update(NotificationModel)
                                  .where(NotificationModel.id == not_id, NotificationModel.to_user_id == user_id)
                                  .values(is_read=True))
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def mark_all_read(user_id: int, db: AsyncSession) -> int:
        result = await db.execute(update(NotificationModel)
                                  .where(NotificationModel.to_user_id == user_id, NotificationModel.is_read.is_(False))
                                  .values(is_read=True))
        await db.commit()
        return result.rowcount
