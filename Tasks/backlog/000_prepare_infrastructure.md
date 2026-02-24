# Задача 000: Подготовка инфраструктуры

## Цель
Обновить конфигурацию, зависимости и БД для Discord. Убедиться что окружение готово.

## Предусловие
Discord-приложение создано вручную на https://discord.com/developers/applications
Токен бота получен и записан.

## Шаги

### 1. Обновить requirements.txt
Заменить `python-telegram-bot[job-queue]==21.0` и `nest_asyncio` на:
```
discord.py>=2.3
```
Остальные зависимости (asyncpg, httpx, SQLAlchemy, alembic, fastapi, uvicorn) — оставить.

### 2. Обновить config_loader.py
Прочитать текущий `Bot/config_loader.py`. Заменить:
- `TELEGRAM_BOT_TOKEN` → `DISCORD_BOT_TOKEN`
- Добавить `DISCORD_GUILD_ID` (int)
- Добавить `DISCORD_ADMIN_ROLE` (str, по умолчанию "BotAdmin")
- Удалить `ADMIN_USER_ID` (заменяется ролью)
- Остальные параметры (GitLab, DB, Camera, TestIT) — без изменений

### 3. Обновить .env
Добавить:
```
DISCORD_BOT_TOKEN=YOUR_TOKEN
DISCORD_GUILD_ID=YOUR_GUILD_ID
DISCORD_ADMIN_ROLE=BotAdmin
```
Убрать TELEGRAM_BOT_TOKEN.

### 4. Обновить config.json
Аналогично — добавить discord_bot_token, discord_guild_id, discord_admin_role. Убрать telegram_bot_token.

### 5. Создать Alembic-миграцию для subscribers
Адаптация таблицы `subscribers` под Discord:
- `chat_id` → `channel_id` (BigInteger)
- `thread_message_id` → `thread_id` (BigInteger)
- `source_type` значения: `dm`, `channel`, `thread` (вместо `private`, `group`, `group_thread`)
- Добавить столбец `guild_id` (BigInteger)

### 6. Создать структуру директорий
```bash
mkdir -p Bot/cogs Bot/views Bot/tasks
touch Bot/cogs/__init__.py Bot/views/__init__.py Bot/tasks/__init__.py
```

## Проверка
- `pip install -r Bot/requirements.txt` без ошибок
- `python -c "import discord; print(discord.__version__)"` выводит версию
- `alembic upgrade head` выполняется без ошибок
- Директории cogs/, views/, tasks/ созданы с __init__.py

## Коммит
```
[init] Подготовка инфраструктуры для Discord-миграции

- requirements.txt: discord.py вместо python-telegram-bot
- config_loader.py: DISCORD_BOT_TOKEN, GUILD_ID, ADMIN_ROLE
- Alembic-миграция: subscribers адаптирована под Discord
- Структура: cogs/, views/, tasks/
```
