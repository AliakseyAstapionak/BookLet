from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core import get_db, redis_client
from .tags import TAG_SERVICE

router = APIRouter(tags=[TAG_SERVICE])


@router.get('/ping', summary='Проверка работы сервиса')
async def ping():
    return {'ok': True}


@router.get('/dbping', summary='Проверка подключения к базе данных')
async def dbping(db: AsyncSession = Depends(get_db)):
    await db.execute(text('SELECT 1'))
    return {'ok': True}


@router.get('/redisping', summary='Проверка подключения к Redis')
async def redis_ping():
    res = await redis_client.ping()
    return {'success': res}
