from pydantic_settings import BaseSettings, SettingsConfigDict

class MailSettings(BaseSettings):
    # ... ваши старые настройки ...
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_FROM: str

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

mailsettings = MailSettings()