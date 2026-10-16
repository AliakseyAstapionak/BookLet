from pydantic_settings import BaseSettings, SettingsConfigDict

class JWTSettings(BaseSettings):

    JWT_SECRET_KEY: str
    JWT_EXPIRE_SECONDS: int
    JWT_ALGORITHM: str
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

jwtsettings = JWTSettings()
