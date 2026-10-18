from email.message import EmailMessage
import aiosmtplib
from settings import mailsettings as settings

class EmailService:

    @staticmethod
    async def _send(message: EmailMessage):
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST, port=settings.SMTP_PORT,
            username=settings.SMTP_USER, password=settings.SMTP_PASSWORD,
            use_tls=False, start_tls=True,
        )

    @staticmethod
    async def send_mail_code(email_to: str, code: str):
        message = EmailMessage()
        message["From"] = settings.SMTP_FROM
        message["To"] = email_to
        message["Subject"] = "Код подтверждения для входа в BookLet"
        
        message.set_content(
            f"Здравствуйте!\n\n"
            f"Ваш код подтверждения для входа: {code}\n"
            f"Код действителен в течение 5 минут.\n\n"
            f"Если вы не запрашивали этот код, просто проигнорируйте это письмо."
        )
        try:
            await EmailService._send(message)
        except Exception as e: # Здесь можно настроить логирование ошибки отправки
            print(f"Ошибка при отправке письма на {email_to}: {e}")


    @staticmethod
    async def send_registration_code(email_to: str, code: str, expire_minutes: int = 10):
        message = EmailMessage()
        message["From"] = settings.SMTP_FROM
        message["To"] = email_to
        message["Subject"] = "Подтверждение почты в BookLet"
        message.set_content(
            f"Здравствуйте!\n\n"
            f"Ваш код для подтверждения регистрации в BookLet: {code}\n"
            f"Код действителен {expire_minutes} минут.\n\n"
            f"Если вы не регистрировались, просто проигнорируйте это письмо."
        )
        try:
            await EmailService._send(message)
        except Exception as e:
            print(f"Ошибка при отправке письма на {email_to}: {e}")


#TODO захардкожено время токена
    @staticmethod
    async def send_reset_password_email(email_to: str, reset_link: str, expire_minutes: int = 5):
        message = EmailMessage()
        message["From"] = settings.SMTP_FROM
        message["To"] = email_to
        message["Subject"] = "Восстановление пароля в BookLet"

        message.set_content(
            f"Здравствуйте!\n\n"
            f"Мы получили запрос на восстановление пароля для вашего аккаунта в BookLet.\n"
            f"Чтобы задать новый пароль, перейдите по ссылке:\n\n"
            f"{reset_link}\n\n"
            f"Ссылка действительна в течение {expire_minutes} минут.\n\n"
            f"Если вы не запрашивали восстановление пароля, просто проигнорируйте это письмо: "
            f"ваш пароль останется прежним."
        )
        try:
            await EmailService._send(message)
        except Exception as e: # Здесь можно настроить логирование ошибки отправки
            print(f"Ошибка при отправке письма на {email_to}: {e}")