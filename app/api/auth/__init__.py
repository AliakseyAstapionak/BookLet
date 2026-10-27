from .registration import router as registration_router
from .login import router as login_router
from .password_reset import router as password_reset_router

# Порядок важен: так группы будут идти в документации
auth_routers = [registration_router, login_router, password_reset_router]
