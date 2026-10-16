from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists, update, not_
from models import UserModel
from typing import Optional

class UserService:

    @staticmethod
    async def existing_username(username: str, db: AsyncSession) -> bool:
        query = select(exists().where(UserModel.username == username))
        result = await db.execute(query)
        return bool(result.scalar())

    @staticmethod
    async def existing_email(email: str, db: AsyncSession) -> bool:
        query = select(exists().where(UserModel.email == email))
        result = await db.execute(query)
        return bool(result.scalar())
        
    @staticmethod
    async def existing_id(id: int, db: AsyncSession) -> bool:
        query = select(exists().where(UserModel.id == id))
        result = await db.execute(query)
        return bool(result.scalar())

    @staticmethod
    async def get_user_by_username(username: str, db: AsyncSession) -> Optional[UserModel]:
        query = select(UserModel).where(UserModel.username == username)
        result = await db.execute(query)
        return result.scalar()

    @staticmethod
    async def get_user_by_id(id: int, db: AsyncSession) -> Optional[UserModel]:
        query = select(UserModel).where(UserModel.id == id)
        result = await db.execute(query)
        return result.scalar()

    @staticmethod
    async def create_user(username: str, email: str, hashed_pwd: str, db: AsyncSession) -> UserModel:
        new_user = UserModel(username=username, email=email.lower(), hashed_pwd=hashed_pwd)
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user  

    @staticmethod
    async def reset_password(uid: int, old_hash: str, new_hashed_pwd: str, db: AsyncSession) -> bool:
        q = (update(UserModel)
            .where(UserModel.id == uid, UserModel.hashed_pwd == old_hash)
            .values(hashed_pwd=new_hashed_pwd))
        result = await db.execute(q)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def change_2fa(user_id: int, db: AsyncSession):
        query = update(UserModel).where(UserModel.id == user_id).values(_2fa=not_(UserModel._2fa))
        result = await db.execute(query)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def get_password_by_username(username: str, db: AsyncSession) -> Optional[str]:
        query = select(UserModel.hashed_pwd).where(UserModel.username == username)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def change_password(user_id: int, new_hash_password: str, db: AsyncSession) -> bool:
        query = update(UserModel).where(UserModel.id == user_id).values(hashed_pwd=new_hash_password)
        result = await db.execute(query)
        await db.commit()
        return result.rowcount > 0