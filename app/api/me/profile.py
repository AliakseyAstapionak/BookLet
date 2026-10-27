from fastapi import APIRouter, Depends, HTTPException, status

from schemas import AccountDataResponseSchema
from services import UserService
from core import get_db
from utils import get_current_user
from ..tags import TAG_PROFILE

router = APIRouter(prefix='/BookLet/me', tags=[TAG_PROFILE])


# TODO нужно подумать как разбединить показ данных для пользователя другого и своего аккаунта потому что что бы на своем акке почта показывалась всегда а на другом только если пользователь открыт
@router.get(
    '',
    response_model=AccountDataResponseSchema,
    summary='Данные моего аккаунта',
    responses={401: {'description': 'Не авторизован'},
               404: {'description': 'Аккаунт не найден'}},
)
async def get_my_data(db=Depends(get_db), current_data=Depends(get_current_user)):
    data = await UserService.get_user_by_id(id=current_data['uid'], db=db)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Аккаунт не найден')
    return {'user': data}
