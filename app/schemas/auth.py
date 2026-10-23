from pydantic import BaseModel, Field, field_validator, EmailStr, ConfigDict
from typing import Optional

class UserRegistrationSchema(BaseModel):
    username: str = Field(min_length=3, max_length=50, description="Имя пользователя")
    email: EmailStr
    password: str = Field(min_length=6, max_length=20, description="Пароль")

    @field_validator('username')
    @classmethod
    def validate_username(cls, value: str):
        if not value.replace('_', '').isalnum():
            raise ValueError("Имя пользователя может содержать только буквы, цифры и _")
        return value

    @field_validator('password')
    @classmethod
    def validate_password(cls, value: str):
        if not any(c.isalpha() for c in value):
            print("Ошибка регистрации: Пароль должен содержать хотя-бы одну букву")
            raise ValueError("Пароль должен содержать хотя-бы одну букву")
        if all(c.isalnum() for c in value):
            print("Ошибка регистрации: Пароль должен содержать хотя-бы один спецсимвол(напр. '!@#$%^&*')")
            raise ValueError("Пароль должен содержать хотя-бы один спецсимвол(напр. '!@#$%^&*')")
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if isinstance(value, str):
            value = value.strip().lower()
            return value or None   
        return value

class UserLoginSchema(BaseModel):
    username: str
    password: str


class UserPublicSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True) 
    id: int
    username: str

class UserPublicActionSchema(BaseModel):
    success: bool
    user: UserPublicSchema

class UserForgotPasswordSchema(BaseModel):
    username: str
    email: str

class ResetPasswordSchema(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=20, description="Новый пароль")

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, value: str):
        if not any(c.isalpha() for c in value):
            print("Ошибка регистрации: Пароль должен содержать хотя-бы одну букву")
            raise ValueError("Пароль должен содержать хотя-бы одну букву")
        if all(c.isalnum() for c in value):
            print("Ошибка регистрации: Пароль должен содержать хотя-бы один спецсимвол(напр. '!@#$%^&*')")
            raise ValueError("Пароль должен содержать хотя-бы один спецсимвол(напр. '!@#$%^&*')")
        return value
    
class ChangePasswordSchema(BaseModel):
    password: str
    new_password: str = Field(min_length=6, max_length=20, description="Новый пароль")

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, value: str):
        if not any(c.isalpha() for c in value):
            print("Ошибка регистрации: Пароль должен содержать хотя-бы одну букву")
            raise ValueError("Пароль должен содержать хотя-бы одну букву")
        if all(c.isalnum() for c in value):
            print("Ошибка регистрации: Пароль должен содержать хотя-бы один спецсимвол(напр. '!@#$%^&*')")
            raise ValueError("Пароль должен содержать хотя-бы один спецсимвол(напр. '!@#$%^&*')")
        return value

class VerifyCodeSchema(BaseModel):
    usercode: str

class Changr2FASchema(BaseModel):
    password: str




