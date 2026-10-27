from .profile import router as profile_router
from .security import router as security_router
from .announcements import router as my_announcements_router
from .favourites import router as favourites_router
from .bookings import router as my_bookings_router
from .notifications import router as notifications_router

# Порядок важен: так группы будут идти в документации
me_routers = [
    profile_router,
    security_router,
    my_announcements_router,
    favourites_router,
    my_bookings_router,
    notifications_router,
]
