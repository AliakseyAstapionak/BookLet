from fastapi import APIRouter, Depends, HTTPException, status, Path
from services import AvailabilityRuleService
from schemas import (MyAccountDataResponseSchema, CreateAvailabilityRuleSchema,
                     AvailabilityResponseSchema, AvailabilityRuleResponseSchema)
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



_UNAUTHORIZED = {401: {'description': 'Не авторизован'}}


@router.get(
    '/operating_mode',
    response_model=AvailabilityResponseSchema,
    summary='Мой режим работы',
    description='Мои окна приёма по дням недели (0 = понедельник). Пустой список значит, что режим не задан.',
    responses=_UNAUTHORIZED,
)
async def get_my_operating_mode(current_user=Depends(get_current_user), db=Depends(get_db)):
    rules = await AvailabilityRuleService.get_operating_mode(user_id=current_user['uid'], db=db)
    return {'rules': rules}


@router.put(
    '/operating_mode',
    response_model=AvailabilityRuleResponseSchema,
    summary='Задать режим работы на день недели',
    description='Задаёт окно приёма на один день недели. Если на этот день окно уже было, оно заменяется. '
                'Остальные дни не затрагиваются.',
    responses=_UNAUTHORIZED,
)
async def set_operating_mode(rule: CreateAvailabilityRuleSchema, current_user=Depends(get_current_user),
                             db=Depends(get_db)):
    res = await AvailabilityRuleService.create_operating_mode(rule=rule, user_id=current_user['uid'], db=db)
    return {'success': True, 'msg': 'Режим работы изменён', 'rule': res}


@router.delete(
    '/operating_mode/{weekday}',
    summary='Убрать день из режима работы',
    description='Удаляет окно приёма на день недели (0 = понедельник): в этот день запись станет недоступна.',
    responses={**_UNAUTHORIZED, 404: {'description': 'На этот день режим не задан'}},
)
async def delete_operating_mode(weekday: int = Path(ge=0, le=6), current_user=Depends(get_current_user),
                                db=Depends(get_db)):
    deleted = await AvailabilityRuleService.delete_operating_mode(weekday=weekday, user_id=current_user['uid'], db=db)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='На этот день режим работы не задан')
    return {'success': True, 'msg': 'День убран из режима работы'}