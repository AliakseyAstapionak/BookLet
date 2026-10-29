from fastapi import APIRouter, Depends, HTTPException, status
from services import AvailabilityRuleService
from schemas import MyAccountDataResponseSchema, CreateAvailabilityRuleSchema
from services import UserService
from core import get_db
from utils import get_current_user
from ..tags import TAG_PROFILE

router = APIRouter(prefix='/BookLet/account/me', tags=[TAG_PROFILE])


# TODO нужно подумать как разбединить показ данных для пользователя другого и своего аккаунта потому что что бы на своем акке почта показывалась всегда а на другом только если пользователь открыт
@router.get(
    '',
    response_model=MyAccountDataResponseSchema,
    summary='Данные моего аккаунта',
    responses={401: {'description': 'Не авторизован'},
               404: {'description': 'Аккаунт не найден'}},
)
async def get_my_data(db=Depends(get_db), current_data=Depends(get_current_user)):
    data = await UserService.get_user_by_id(id=current_data['uid'], with_settings=True, db=db)
    if not data or data.is_active == False:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Аккаунт не найден')
    return {'user': data, 'settings': data.settings}

@router.post('/set_operating_mode')
async def create_operating_mode(rule: CreateAvailabilityRuleSchema ,current_user=Depends(get_current_user), db=Depends(get_db)):
    res = await AvailabilityRuleService.create_operating_mode(rule=rule, user_id=current_user['uid'], db=db)
    return {'success': True, 'msg': 'Режим работы изменен', 'rule': res}
