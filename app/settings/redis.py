from pydantic_settings import BaseSettings, SettingsConfigDict

class RedisSettings(BaseSettings):
    REDIS_HOST: str
    REDIS_PORT: int

    model_config=SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

redissettings = RedisSettings()