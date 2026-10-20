from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core import get_db, redis_client
from sqlalchemy import text

router = APIRouter()


@router.get('/ping')
async def ping():
    return {'ok': True}

@router.get('/dbping')
async def dbping(db: AsyncSession = Depends(get_db)):
    await db.execute(text('SELECT 1'))
    return {'ok': True}

@router.get('/redisping')
async def ping():
    res = await redis_client.ping()
    return {'success': res}
    
    
    