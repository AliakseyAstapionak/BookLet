from .auth import auth_routers
from .catalog import router as catalog_router
from .reviews import router as reviews_router
from .users import router as user_router
from .me import me_routers
from .health import router as health_router
from .tags import openapi_tags

routers = [
    *auth_routers,
    catalog_router,
    reviews_router,
    user_router,
    *me_routers,
    health_router,
]

__all__ = ['routers', 'openapi_tags']
