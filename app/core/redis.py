import redis.asyncio as aioredis
from  settings import redissettings

redis_client = aioredis.Redis(host=redissettings.REDIS_HOST, port=redissettings.REDIS_PORT, db=0, decode_responses=True )