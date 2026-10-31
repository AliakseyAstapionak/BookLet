<div align="center">

# 📚 BookLet

**Backend сервиса онлайн-записи к мастерам: каталог услуг, расписание, бронирование без накладок, отзывы и уведомления.**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-cache-DC382D?logo=redis&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0_async-D71F00)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

</div>

---

## О проекте

**BookLet** — сервис записи по времени. Мастер публикует услугу, задаёт рабочие часы по дням недели, а клиенты видят свободные слоты и записываются в один клик. Система сама следит, чтобы два клиента не заняли одно время, а мастер и клиент получали уведомления о каждом событии.

Это backend-часть проекта (моя зона ответственности). Простой демо-интерфейс лежит в `app/static` и отдаётся самим приложением, чтобы всё можно было потрогать без отдельного фронтенд-сервера.

### Что умеет

| Блок | Возможности |
|---|---|
| **Аккаунты** | Регистрация с подтверждением почты, вход, необязательная 2FA по email, сброс пароля по ссылке, смена пароля |
| **Каталог** | Поиск и фильтры (название, тип, цена, мастер), 4 вида сортировки, пагинация, избранное |
| **Расписание** | Рабочие окна мастера по дням недели, автоматический расчёт свободных слотов, личный календарь |
| **Бронирование** | Запись на слот, отмена клиентом (с дедлайном) и мастером (в любой момент), защита от двойной записи на уровне БД |
| **Отзывы** | Только после состоявшейся услуги, один отзыв на бронь, средний рейтинг |
| **Фото** | До 5 фото на объявление, валидация содержимого|
| **Уведомления** | Входящие и отправленные, счётчик непрочитанных, «прочитать все» |
| **Сервис** | Swagger с группами и описаниями, health-эндпоинты для БД и Redis |

---

## Стек

| Слой | Технологии |
|---|---|
| Язык и фреймворк | Python 3.11+, **FastAPI**, Uvicorn |
| База данных | **PostgreSQL 15**, **SQLAlchemy 2.0** (async) + **asyncpg** |
| Кэш и временные данные | **Redis** (`redis.asyncio`) |
| Безопасность | **PyJWT** (токены в httpOnly cookie), **bcrypt**, HMAC-SHA256 |
| Валидация и конфиг | **Pydantic v2**, **pydantic-settings** (`.env`) |
| Почта | **aiosmtplib** (SMTP) |
| Изображения | **Pillow** |
| Инфраструктура | Docker, Docker Compose |
| Демо-фронтенд | Vanilla JS SPA (без сборки), раздаётся из `app/static` |

---

## Архитектура

Проект разделён на слои с одной зоной ответственности у каждого:

```
HTTP-запрос
    │
    ▼
┌──────────┐   валидация, cookie, коды ответов, документация OpenAPI
│   api    │   (тонкие роутеры, без бизнес-логики)
└────┬─────┘
     ▼
┌──────────┐   вся бизнес-логика: правила бронирования, слоты, отзывы
│ services │   (статические сервисы, транзакции, HTTPException)
└────┬─────┘
     ▼
┌──────────┐        ┌──────────┐
│  models  │ ─────▶ │ Postgres │   ограничения целостности живут в БД
└──────────┘        └──────────┘
     ▲
     │  utils/auth — токены, 2FA, лимиты  ─────▶  Redis
```

```
app/
├── main.py              # сборка приложения, lifespan, раздача статики и /uploads
├── api/                 # роутеры (auth/, me/, catalog, reviews, users, health, tags)
├── services/            # бизнес-логика (booking, slots, calendar, reviews, photo, ...)
├── models/              # SQLAlchemy-модели и ограничения БД
├── schemas/             # Pydantic-схемы запросов и ответов
├── utils/               # пароли, JWT, 2FA, rate limit
├── core/                # engine, сессии, Redis-клиент, пути
├── settings/            # конфигурация из .env (по классу на подсистему)
└── static/              # демо-интерфейс
```

### Модель данных

```
users ──< announcements ──< announcement_photos
  │            │
  │            └──< bookings >── users (client / provider)
  │                    │
  │                    ├──< reviews   (1 отзыв на бронь)
  │                    └──< notifications
  ├── user_settings        (2FA, показ email)
  ├── availability_rules   (окно приёма на день недели)
  └── user_liked_announcements (избранное, M:N)
```

---

## Ключевые технические решения

### 1. Бронирование без гонок: защита на уровне PostgreSQL
Проверки в коде недостаточны: два запроса могут одновременно увидеть слот свободным. Поэтому последний рубеж стоит в базе, это `EXCLUDE USING gist` с диапазоном времени:

```python
ExcludeConstraint(
    ('provider_id', '='),
    (text("tstzrange(start_at, end_at, '[)')"), '&&'),
    where=text("status IN ('PENDING', 'CONFIRMED')"),
    name='ex_provider_no_overlap', using='gist',
)
```

Для одного мастера активные брони физически не могут пересекаться. Приложение ловит `IntegrityError` и отдаёт аккуратный `409`. Отменённые брони в ограничение не попадают, поэтому освободившееся время сразу доступно снова.

### 2. Слоты считаются на лету
Свободные слоты не хранятся, а вычисляются из рабочих окон мастера (`availability_rules`) за вычетом активных броней. Нечего синхронизировать и нечему «протухнуть». Все вычисления идут в timezone-aware datetime (`Europe/Moscow`), на запись принимается только время, которое строго совпадает с сеткой слотов.

### 3. Снимок условий в брони
В `bookings` копируются `price` и `cancel_before_hours` на момент записи. Если мастер потом поднимет цену или ужесточит правила, уже сделанные брони не изменятся.

### 4. Атомарность и защита от двойных действий
- Бронь и уведомление мастеру сохраняются **одним коммитом** (`commit=False` + общий `db.commit()`): не бывает брони без уведомления и наоборот.
- Отмена — условный `UPDATE … WHERE status IN (активные)` с проверкой `rowcount`: повторная или параллельная отмена безопасно даёт `409`.
- Сброс пароля: `UPDATE … WHERE hashed_pwd = <старый хеш>` исключает гонку двух смен пароля.

### 5. Безопасность аутентификации
- **JWT в httpOnly cookie** (`SameSite=Lax`), недоступны из JavaScript.
- **Типизированные токены**: `access`, `2fa`, `registration`, `reset_pwd`. Токен одного типа не подходит для другого.
- **bcrypt (12 раундов)** вынесен в `asyncio.to_thread`, чтобы не блокировать event loop; учтён лимит bcrypt в 72 байта.
- **2FA-коды хранятся только в виде HMAC-SHA256** с секретом сервера, сравниваются через `hmac.compare_digest` (без утечки по времени), живут 5 минут, 3 попытки. Счётчик попыток уменьшается атомарно через `HINCRBY`.
- **Cooldown на отправку кода** (60 с) реализован через `SET NX EX`, это атомарно и не требует блокировок.
- **Rate limit** неудачных входов и регистраций: 5 попыток за окно 10 минут с одного IP, счётчики в Redis.
- **Одноразовая ссылка сброса пароля без хранения состояния**: в токен зашит «отпечаток» текущего хеша пароля. После смены пароля отпечаток не совпадает, и ссылка мертва.
- Единые обобщённые ответы в сбросе пароля, чтобы не раскрывать, какие данные неверны.

### 6. Регистрация без мусора в БД
На первом шаге данные (с уже посчитанным bcrypt-хешем, не паролем) лежат в Redis с TTL 10 минут. Пользователь создаётся в Postgres **только после подтверждения почты**. Нет неподтверждённых аккаунтов и «захваченных» чужих адресов.

### 7. Безопасная работа с файлами
- Содержимое файла проверяется через **Pillow** (`verify()`), а не по расширению или заголовку; разрешены только JPEG/PNG/WEBP.
- Имена файлов — `uuid4`, пользовательское имя на диск не попадает (нет path traversal и коллизий).
- Лимит 5 МБ читается с отсечением (`read(MAX+1)`), файл не грузится в память целиком.
- Если запись в БД упала, файл с диска удаляется — нет «осиротевших» файлов.
- Раздача `/uploads` с `Cache-Control: immutable` на год и `nosniff`: имя уникально, содержимое не меняется.
- Блокирующий файловый ввод-вывод вынесен в `asyncio.to_thread`.

### 8. Отзывы только по делу
Отзыв можно оставить лишь на бронь клиента, которая **уже состоялась** (`end_at <= now`), и только один раз (`UNIQUE(booking_id)`), рейтинг ограничен `CHECK (1..5)`. Правила продублированы в БД, поэтому остаются верными даже при обходе API.

### 9. Полностью асинхронный стек
Postgres (`asyncpg`), Redis (`redis.asyncio`), SMTP (`aiosmtplib`) и файловый I/O не блокируют event loop. Письма уходят через `BackgroundTasks`, поэтому ответ пользователю не ждёт SMTP-сервер.

### 10. Аккуратный API
56 эндпоинтов, сгруппированных по темам с описаниями и кодами ошибок в Swagger. Пагинация с верхним лимитом, сортировка с тай-брейкером по `id` (стабильный порядок), обработка ошибок через осмысленные HTTP-статусы. Конфигурация через `pydantic-settings`, никаких секретов в коде.

---

## Быстрый старт

### Требования
Python 3.11+, PostgreSQL 15+, Redis, SMTP-аккаунт для отправки писем (подойдёт любой, например Gmail с паролем приложения или Mailtrap для тестов).

### 1. Клонирование и зависимости

```bash
git clone <URL-репозитория>
cd <папка-проекта>

python -m venv venv
# Windows:  venv\Scripts\activate
# Linux/macOS:  source venv/bin/activate

pip install fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" asyncpg \
            pydantic-settings "pydantic[email]" redis bcrypt PyJWT \
            aiosmtplib Pillow python-multipart
```

> Рекомендуется зафиксировать версии командой `pip freeze > requirements.txt`.

### 2. Конфигурация

Создайте файл `.env` в папке `app/` (рядом с `main.py`):

```env
# PostgreSQL
DB_NAME=booklet
DB_USER=postgres
DB_PASS=postgres
DB_HOST=127.0.0.1
DB_PORT=5432

# Redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379

# JWT
JWT_SECRET_KEY=замените-на-длинную-случайную-строку
JWT_ALGORITHM=HS256
JWT_EXPIRE_SECONDS=3600

# SMTP (STARTTLS)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=user@example.com
SMTP_PASSWORD=пароль-приложения
SMTP_FROM=BookLet <user@example.com>
```

Сгенерировать секрет: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

Необязательно: `UPLOAD_DIR` — путь для загруженных фото (по умолчанию `app/uploads`).

### 3. База данных и Redis

Быстрее всего поднять зависимости в Docker:

```bash
docker run -d --name booklet_db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=booklet \
           -p 5432:5432 postgres:15
docker run -d --name booklet_redis -p 6379:6379 redis:7
```

> Если порт 6379 занят локальным Redis/Memurai, пробросьте другой (`-p 6380:6379`) и поменяйте `REDIS_PORT`.

### 4. Создание таблиц

Для ограничения на пересечение броней нужно расширение `btree_gist`. Создайте файл `app/init_db.py` и запустите его один раз:

```python
import asyncio
from sqlalchemy import text

import models  # noqa: F401  (регистрирует все таблицы)
from core import engine, Base


async def main():
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS btree_gist'))
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print('Таблицы созданы')

asyncio.run(main())
```

```bash
cd app
python init_db.py
```

### 5. Запуск

```bash
cd app
uvicorn main:app --reload
```

| Что | Адрес |
|---|---|
| Демо-интерфейс | http://127.0.0.1:8000 |
| Swagger UI | http://127.0.0.1:8000/docs |
| ReDoc | http://127.0.0.1:8000/redoc |
| Проверка сервиса | `/ping`, `/dbping`, `/redisping` |

### Запуск в Docker Compose

Приложение рассчитано на запуск в контейнере вместе с `db` и `redis`. Внутри compose-сети укажите в `.env` имена сервисов: `DB_HOST=db`, `REDIS_HOST=redis` (а не `127.0.0.1`: внутри контейнера `127.0.0.1` — это он сам).

```bash
docker compose up --build
```

---

## Как пользоваться (сценарий за 2 минуты)

1. **Регистрация:** `POST /BookLet/registration` → код приходит на почту → `POST /BookLet/registration/verify_email`.
2. **Вход:** `POST /BookLet/login` (cookie `access_token` ставится автоматически).
3. **Мастеру:** создать услугу `POST /BookLet/me/my_announcements/create` и задать рабочие часы `PUT /BookLet/account/me/operating_mode`.
4. **Клиенту (другой аккаунт):** `GET /BookLet/catalog` → `GET /BookLet/catalog/{id}/slots` → `POST /BookLet/catalog/{id}/book?start_at=...`.
5. Мастер видит уведомление и запись в календаре: `GET /BookLet/account/me/calendar`.
6. После оказания услуги клиент оставляет отзыв: `POST /BookLet/catalog/{id}/reviews`.

---

## Карта API (основные группы)

| Группа | Префикс | Примеры |
|---|---|---|
| Регистрация | `/BookLet/registration` | заявка, подтверждение почты, повторная отправка кода |
| Вход и выход | `/BookLet/login`, `/logout` | вход, `/login/2fa`, `/login/2fa/resend` |
| Пароль | `/BookLet/forgot_password`, `/reset_password` | запрос ссылки, установка нового пароля |
| Каталог | `/BookLet/catalog` | список, карточка, фото, слоты, лайк, бронь |
| Отзывы | `/BookLet/catalog/{id}/reviews` | список со средним рейтингом, создание |
| Профили | `/BookLet/user/{id}` | профиль, объявления, режим работы |
| Мой аккаунт | `/BookLet/account/me` | данные, режим работы, календарь |
| Безопасность | `/BookLet/me/account/settings/security` | 2FA, показ email, смена пароля |
| Мои объявления | `/BookLet/me/my_announcements` | создание, архив, фото, записи ко мне, отмена мастером |
| Мои брони | `/BookLet/me/my_bookings` | список, отмена клиентом |
| Избранное | `/BookLet/me/my_favourites` | список избранного |
| Уведомления | `/BookLet/me/my_notifications` | входящие, отправленные, счётчик, прочитано |

Полная интерактивная документация с примерами и кодами ответов — в Swagger (`/docs`).

---

## Правила бронирования

- Бронировать можно только свободный слот из `/slots`, не в прошлом и не дальше чем на 31 день вперёд.
- Нельзя записаться на своё объявление.
- **Клиент** может отменить бронь не позднее чем за `cancel_before_hours` до начала; **мастер** — в любой момент до начала.
- Время отменённой брони сразу снова доступно для записи.
- Вторая сторона получает уведомление о каждой брони и отмене.

---

## Дальнейшее развитие
- Подтверждение брони мастером (статус `PENDING` уже заложен в модели и в ограничении БД)
- Автоматический перевод броней в `COMPLETED` и напоминания перед услугой (планировщик)
- Часовой пояс у каждого мастера вместо одного на сервис
- Очередь задач (arq/Celery) для писем, структурное логирование
- Автотесты (pytest + httpx) и CI

---

## Автор

Aliaksey Astapionak — backend-разработка (архитектура, БД, API, безопасность).
Контакты: tg: @AliakseyAstapional