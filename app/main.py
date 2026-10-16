from fastapi import FastAPI
from core import engine, Base, redis_client
import uvicorn
from contextlib import asynccontextmanager
from api import auth_router, user_router

#TODO проверить на is_active
#TODO подумать как обощить rpslimeter чтобы не переписывать его на каждую функцию

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    await redis_client.close()
    print('Приложение остановлено!')


app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)
app.include_router(user_router)


if __name__ == '__main__':
    uvicorn.run('main:app', host='127.0.0.1', port=8000, reload=True)