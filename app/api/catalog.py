from fastapi import APIRouter, Depends, Query
from core import get_db
from services import AnnouncementService
from typing import Annotated
from schemas import AnnouncementFiltersSchema
router = APIRouter(prefix='/BookLet', tags=['Каталог'])


@router.get('/catalog')
async def catalog(filters: Annotated[AnnouncementFiltersSchema, Query()],db=Depends(get_db)):
    result = await AnnouncementService.get_catalog(filters=filters, db=db)
    return {'announcements': result}