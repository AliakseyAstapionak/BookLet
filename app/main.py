from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from core import engine, Base, redis_client
from core.paths import UPLOAD_DIR
import uvicorn
from contextlib import asynccontextmanager
from api import routers, openapi_tags


class UploadFiles(StaticFiles):
    """Загруженные фото: имена — uuid, содержимое не меняется, поэтому кэшируем надолго."""
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if resp.status_code in (200, 304):
            resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            resp.headers['X-Content-Type-Options'] = 'nosniff'
        return resp

#TODO подумать как обощить rpslimeter чтобы не переписывать его на каждую функцию
#TODO подумать как лучше реализовать наказание за неприход или что то такое 
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
    await redis_client.close()
    print('Приложение остановлено!')


app = FastAPI(
    title='BookLet API',
    description='API сервиса бронирования услуг BookLet.\n\n'
                'Авторизация — через cookie `access_token`, которую ставит `/BookLet/login`. '
                'Ручки, помеченные в описании группы «Требуется авторизация», без неё вернут 401.',
    openapi_tags=openapi_tags,
    lifespan=lifespan,
)

# Порядок роутеров = порядок групп в документации (см. api/__init__.py и api/tags.py)
for router in routers:
    app.include_router(router)

# ---------- Фронтенд (папка static рядом с main.py) ----------
STATIC_DIR = Path(__file__).parent / 'static'
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
# Фото объявлений. Монтируем ДО catch-all, иначе /uploads/... отдаст index.html
app.mount('/uploads', UploadFiles(directory=UPLOAD_DIR), name='uploads')


@app.get('/{full_path:path}', include_in_schema=False)
async def frontend(full_path: str):
    """Отдаёт SPA для любых путей, не занятых API (/BookLet/*, /docs, /ping и т.д.).
    Нужен в том числе для ссылки сброса пароля: /reset_password?reset_token=..."""
    if full_path.startswith('BookLet/'):
        raise HTTPException(status_code=404, detail='Not Found')
    return FileResponse(STATIC_DIR / 'index.html')


#TODO подумать над выполнением брони
if __name__ == '__main__':
    uvicorn.run('main:app', host='127.0.0.1', port=8000, reload=True)