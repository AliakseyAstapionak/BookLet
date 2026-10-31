import asyncio
import io
import uuid

from fastapi import HTTPException, status
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.paths import UPLOAD_DIR
from models import AnnouncementPhotoModel

MAX_ANNOUNCEMENT_PHOTOS = 5
ALLOWED_FORMATS = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}


class PhotoService:

    @staticmethod
    async def get_announcement_photos(anc_id: int, db: AsyncSession) -> list[AnnouncementPhotoModel]:
        query = (select(AnnouncementPhotoModel)
                 .where(AnnouncementPhotoModel.announcement_id == anc_id)
                 .order_by(AnnouncementPhotoModel.created_at.asc(), AnnouncementPhotoModel.id.asc()))
        return list((await db.execute(query)).scalars().all())


    @staticmethod
    async def add_announcement_photo(anc_id: int, data: bytes, db: AsyncSession) -> AnnouncementPhotoModel:
        count = (await db.execute(
            select(func.count()).select_from(AnnouncementPhotoModel)
            .where(AnnouncementPhotoModel.announcement_id == anc_id))).scalar_one()
        if count >= MAX_ANNOUNCEMENT_PHOTOS:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                detail=f'Нельзя добавить больше {MAX_ANNOUNCEMENT_PHOTOS} фото')

        try:
            img = Image.open(io.BytesIO(data))
            img.verify()
            fmt = img.format
        except Exception:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Файл не является изображением')
        if fmt not in ALLOWED_FORMATS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Нужен файл JPEG, PNG или WEBP')

        name = f'{uuid.uuid4().hex}.{ALLOWED_FORMATS[fmt]}'
        path = UPLOAD_DIR / name
        await asyncio.to_thread(path.write_bytes, data)

        photo = AnnouncementPhotoModel(announcement_id=anc_id, filename=name)
        db.add(photo)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            await asyncio.to_thread(path.unlink, True)
            raise
        await db.refresh(photo)
        return photo

    @staticmethod
    async def delete_announcement_photo(anc_id: int, photo_id: int, db: AsyncSession) -> None:
        photo = (await db.execute(
            select(AnnouncementPhotoModel).where(
                AnnouncementPhotoModel.id == photo_id,
                AnnouncementPhotoModel.announcement_id == anc_id))).scalar()
        if photo is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Фото не найдено')

        name = photo.filename
        await db.delete(photo)
        await db.commit()
        await asyncio.to_thread((UPLOAD_DIR / name).unlink, True)