from typing import Literal, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from models import AnnouncementModel, StatusEnum, UserModel, user_liked_announcements
from schemas import AnnouncementFiltersSchema, AnnouncementResponseSchema, SortEnum, MyAnnouncementFiltersSchema

SORT_MAP = {
    SortEnum.NEWEST:     (AnnouncementModel.created_at.desc(), AnnouncementModel.id.desc()),
    SortEnum.PRICE_ASC:  (AnnouncementModel.price.asc(), AnnouncementModel.id.asc()),
    SortEnum.PRICE_DESC: (AnnouncementModel.price.desc(), AnnouncementModel.id.asc()),
    SortEnum.NAME:       (AnnouncementModel.name.asc(), AnnouncementModel.id.asc()),
}

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
    
    @staticmethod
    async def existing_anouncement(id: int, db: AsyncSession) -> bool:
        query = select(AnnouncementModel).where(AnnouncementModel.id == id) 
        result = await db.execute(query)
        return bool(result.scalar())

    @staticmethod
    async def get_announcement_name(id: int, db: AsyncSession):
        query = select(AnnouncementModel.name).where(AnnouncementModel.id == id) 
        result = await db.execute(query)
        return result.scalar()


    @staticmethod
    async def get_my_announcements(user_id: int, filters: MyAnnouncementFiltersSchema, status: Literal['active', 'archived', 'booked'], db: AsyncSession, limit: int = 20, offset: int = 0) -> AnnouncementResponseSchema :
        query = select(AnnouncementModel).where(AnnouncementModel.status == status, AnnouncementModel.user_id == user_id)
        if filters.name:
            query = query.where(AnnouncementModel.name.ilike(f"%{filters.name}%"))
        if filters.type:
            query = query.where(AnnouncementModel.type == filters.type)
        if filters.min_price:
            query = query.where(AnnouncementModel.price >= filters.min_price)
        if filters.max_price:
            query = query.where(AnnouncementModel.price <= filters.max_price)
        query = query.order_by(*SORT_MAP[filters.sort]).limit(filters.limit).offset(filters.offset)
        result = await db.execute(query)
        return result.scalars().all()

    
    @staticmethod
    async def get_liked_user_announcements(filters: MyAnnouncementFiltersSchema, uid: int, db: AsyncSession):
        query = (select(AnnouncementModel).join(user_liked_announcements, AnnouncementModel.id == user_liked_announcements.c.announcement_id
                ).where(user_liked_announcements.c.user_id == uid))
        if filters.name:
            query = query.where(AnnouncementModel.name.ilike(f"%{filters.name}%"))
        if filters.type:
            query = query.where(AnnouncementModel.type == filters.type)
        if filters.min_price:
            query = query.where(AnnouncementModel.price >= filters.min_price)
        if filters.max_price:
            query = query.where(AnnouncementModel.price <= filters.max_price)
        query = query.order_by(*SORT_MAP[filters.sort]).limit(filters.limit).offset(filters.offset)
        result = await db.execute(query)
        return result.scalars().all()


    @staticmethod
    async def get_my_announcement(user_id: int, anc_id: int, status: StatusEnum, db: AsyncSession):
        query = select(AnnouncementModel).where(AnnouncementModel.id == anc_id, AnnouncementModel.user_id == user_id, AnnouncementModel.status == status)
        result = await db.execute(query)
        return result.scalar()
    
    @staticmethod
    async def delete_announcement(id: int, db: AsyncSession) -> bool:
        query = update(AnnouncementModel).where(AnnouncementModel.id == id, AnnouncementModel.status == StatusEnum.ACTIVE).values(status=StatusEnum.ARCHIVED)
        result = await db.execute(query)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def get_catalog(filters: AnnouncementFiltersSchema, db: AsyncSession) -> AnnouncementResponseSchema:
        query = select(AnnouncementModel).where(AnnouncementModel.status == 'active')
        if filters.name:
            query = query.where(AnnouncementModel.name.ilike(f"%{filters.name}%"))
        if filters.type:
            query = query.where(AnnouncementModel.type == filters.type)
        if filters.min_price:
            query = query.where(AnnouncementModel.price >= filters.min_price)
        if filters.max_price:
            query = query.where(AnnouncementModel.price <= filters.max_price)
        if filters.provider:
            query = query.join(UserModel).where(UserModel.username == filters.provider)
        query = query.order_by(*SORT_MAP[filters.sort]).limit(filters.limit).offset(filters.offset)
        result = await db.execute(query)
        return result.scalars().all()


