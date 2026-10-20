from typing import Literal, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from models import AnnouncementModel, StatusEnum, UserModel


class AnnouncementService:
    
    @staticmethod
    async def create_announcement(user_id: str, name: str, status: Literal['active', 'archived', 'booked'], type: str, price: int, db: AsyncSession, description: str | None = None):
        new_anc = AnnouncementModel(user_id=user_id, name=name, status=status, type=type, price=price, description=description)
        db.add(new_anc)
        await db.commit()
        await db.refresh(new_anc)
        return new_anc 

    @staticmethod
    async def get_announcement(id: int, db: AsyncSession) -> AnnouncementModel:
        query = select(AnnouncementModel).where(AnnouncementModel.id == id) 
        result = await db.execute(query)
        return result.scalar()

    @staticmethod
    async def get_announcement_user(id: int, db: AsyncSession) -> int | None:
        query = select(AnnouncementModel.user_id).where(AnnouncementModel.id == id)
        result = await db.execute(query)
        return result.scalar()


# TODO добавить фильтры и тп
    @staticmethod
    async def get_my_announcements(user_id: int, db: AsyncSession, limit: int = 20, offset: int = 0) -> List[AnnouncementModel]:
        query = (select(AnnouncementModel)
                .where(AnnouncementModel.user_id == user_id)
                .order_by(AnnouncementModel.created_at.desc(), AnnouncementModel.id.desc())
                .limit(limit)
                .offset(offset))
        result = await db.execute(query)
        return result.scalars().all()


    @staticmethod
    async def delete_announcement(id: int, db: AsyncSession):
        query = update(AnnouncementModel).where(AnnouncementModel.id == id, AnnouncementModel.status == StatusEnum.ACTIVE).values(status=StatusEnum.ARCHIVED)
        result = await db.execute(query)
        await db.commit()
        return result.rowcount > 0