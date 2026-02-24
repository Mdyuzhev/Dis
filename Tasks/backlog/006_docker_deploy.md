# Задача 006: Docker и деплой

## Цель
Обновить Docker-инфраструктуру, задеплоить Discord-бота, мигрировать данные.

## Зависимости
Задачи 000-005 выполнены (весь функционал реализован).

## Контекст
Прочитать:
- `Bot/Dockerfile`, `Bot/Dockerfile.base`, `Bot/Dockerfile_webhook`
- `Bot/docker-compose.yml` и корневой `docker-compose.yml`
- Текущую конфигурацию контейнеров

## Шаги

### 1. Обновить Bot/Dockerfile
```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "discord_bot.py"]
```
Удалить `Dockerfile.base` и `Dockerfile_webhook` если используется единый процесс (бот + вебхук в одном).

### 2. Обновить docker-compose.yml
Заменить сервис `telegram-bot` на `discord-bot`.
Обновить переменные окружения (DISCORD_BOT_TOKEN вместо TELEGRAM).
Порт вебхука (8000) оставить.
Убедиться что PostgreSQL сервис на месте.

### 3. Стратегия запуска вебхука
Рекомендация: **один процесс** — в `discord_bot.py` событие `on_ready` запускает uvicorn через `asyncio.create_task`. Проще для деплоя.

### 4. Миграция данных
Если нужна привязка существующих пользователей:
- Команда `/register` — пользователь вводит, бот связывает Discord ID с профилем
- Или SQL-скрипт для переназначения user_id на Discord ID

### 5. Очистка Telegram-файлов
После успешного деплоя и проверки — удалить:
- `telegram_bot.py`
- `handlers.py`
- `menus.py`
- `format_messages.py`
- `jobs.py`
- `property_editor.py` (если логика перенесена в Modal)

## Проверка
- `docker-compose up --build -d` без ошибок
- Бот подключается к Discord (логи)
- Вебхук слушает на порту 8000
- БД доступна из контейнера

## Коммит
```
[docker] Docker-инфраструктура для Discord-бота

- Dockerfile: python 3.13, discord_bot.py
- docker-compose.yml: сервис discord-bot
- Очистка Telegram-файлов
```
