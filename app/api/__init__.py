"""Роутеры API, сгруппированные по функциональности.

Порядок в `routers` определяет порядок групп в Swagger (/docs):
сначала вход в систему, затем каталог, затем личный кабинет, в конце служебные ручки.
Описания групп лежат в `api/tags.py`.

    api/
    ├── auth/            регистрация, вход/выход, восстановление пароля
    ├── catalog.py       каталог, лайк, бронирование
    ├── users.py         публичные профили других пользователей
    ├── me/              личный кабинет: профиль, безопасность, объявления,
    │                    избранное, брони, уведомления
    ├── health.py        служебные проверки
    └── tags.py          порядок и описание тегов OpenAPI
"""
from .auth import auth_routers
from .catalog import router as catalog_router
from .users import router as user_router
from .me import me_routers
from .health import router as health_router
from .tags import openapi_tags

routers = [
    *auth_routers,
    catalog_router,
    user_router,
    *me_routers,
    health_router,
]

__all__ = ['routers', 'openapi_tags']
