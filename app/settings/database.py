from pydantic_settings import BaseSettings, SettingsConfigDict



class DBSettings(BaseSettings):
    DB_NAME: str
    DB_USER: str
    DB_PASS: str
    DB_HOST: str
    DB_PORT: str

    @property
    def DB_URL(self) -> str:
        return f'postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}'
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

dbsettings = DBSettings()