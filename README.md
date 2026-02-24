# GitLab Monitor Bot for Discord

Discord-бот для мониторинга GitLab-проектов: пайплайны, MR, камеры, Test IT статистика, админ-панель.

> Миграция с Telegram (`python-telegram-bot`) на Discord (`discord.py>=2.3`). Бизнес-логика сохранена, переписан транспортный слой.

---

## Возможности

### Мониторинг пайплайнов
- Автоматические уведомления о запуске и завершении пайплайнов
- Определение стенда (p1, staging, demo, prod) по расписанию и переменным
- Интеграция с Allure: статистика тестов, ссылки на отчёты
- История пайплайнов, расписания, ручной запуск

### Merge Requests
- Отслеживание новых MR и изменений статуса (opened, merged, closed)
- Уведомления подписчикам проекта

### Камеры
- Мониторинг статусов: VCF-Online, AV-Active, AV-Online, VUF
- Обнаружение новых камер
- Отслеживание трансферов между аккаунтами
- Расхождения в учёте камер

### Test IT
- Вебхук для событий Test IT (создание/изменение/удаление тест-кейсов)
- Ежедневная статистика с рейтингом участников
- Настройка весов событий и периода подсчёта
- Управление участниками (включение/выключение)

### Админ-панель
- Запросы на доступ (approve/reject с DM-уведомлением)
- Управление пользователями (ban/unban)
- Гибридная авторизация: Discord-роли + white_list в БД

---

## Архитектура

```
Bot/
├── discord_bot.py              # Точка входа, GitLabBot class
├── config_loader.py            # Конфигурация из config.json + .env
├── db_operations.py            # asyncpg подключение к БД
├── gitlab_api.py               # GitLab REST API клиент
├── embeds.py                   # Discord Embed форматирование + рассылка
├── utils.py                    # Определение стенда, Allure-обогащение
├── scheduler.py                # Планировщик статистики Test IT
├── models.py                   # SQLAlchemy модели
│
├── cogs/                       # Slash-команды
│   ├── general.py              #   /start, /help, /request_access
│   ├── subscriptions.py        #   /subscribe
│   ├── pipelines.py            #   /pipelines [project]
│   ├── admin.py                #   /admin panel|requests|users|testit
│   └── testit.py               #   /testit
│
├── views/                      # Discord UI компоненты
│   ├── main_menu.py            #   Главное меню (persistent)
│   ├── subscription_views.py   #   Подписки: проекты, камеры, Test IT
│   ├── pipeline_views.py       #   Пайплайны, расписания, Allure, .properties
│   ├── admin_views.py          #   Запросы, пользователи
│   └── testit_views.py         #   Участники, период, веса
│
├── tasks/                      # Фоновые задачи (discord.ext.tasks)
│   ├── pipeline_checker.py     #   Пайплайны (300с) + MR (300с)
│   ├── camera_checker.py       #   Статусы (300с) + трансферы + расхождения
│   └── stats_sender.py         #   Ежедневная статистика Test IT (60с check)
│
├── helpers/
│   └── testit_event_service.py # Бизнес-логика событий Test IT
│
├── testit_webhook.py           # FastAPI /testit-webhook endpoint
├── alembic/                    # Миграции БД (12 ревизий)
├── Dockerfile                  # python:3.13-slim
├── docker-compose.yml          # discord-bot + postgres:15
├── config.json                 # Основная конфигурация
├── .env                        # Секреты и переменные окружения
└── requirements.txt            # Зависимости
```

---

## Slash-команды

| Команда | Описание | Доступ |
|---------|----------|--------|
| `/start` | Главное меню | Все (с проверкой white_list) |
| `/help` | Справка по командам | Все |
| `/request_access` | Запрос доступа к боту | Все |
| `/subscribe` | Управление подписками | Одобренные + админы |
| `/pipelines [project]` | Пайплайны, отчёты, расписания | Одобренные + админы |
| `/admin panel` | Админ-панель | Роль BotAdmin |
| `/admin requests` | Запросы на доступ | Роль BotAdmin |
| `/admin users` | Управление пользователями | Роль BotAdmin |
| `/admin testit` | Настройки Test IT | Роль BotAdmin |
| `/testit` | Быстрый доступ к Test IT | Роль BotAdmin |

---

## Фоновые задачи

| Задача | Интервал | Описание |
|--------|----------|----------|
| `check_pipelines_task` | 300с | Новые/завершённые пайплайны → уведомления |
| `check_mrs_task` | 300с | Новые/изменённые MR → уведомления |
| `check_camera_statuses_task` | 300с | Статусы камер: online/offline |
| `check_camera_transfers_task` | 300с | Трансферы камер между аккаунтами |
| `check_camera_discrepancies_task` | 300с | Расхождения в учёте камер |
| `check_stats_schedule_task` | 60с | Проверка времени отправки статистики Test IT |

---

## Быстрый старт

### Требования
- Python 3.13+
- PostgreSQL 15
- Discord-приложение с Bot Token

### 1. Настройка Discord-приложения

1. Создайте приложение на [Discord Developer Portal](https://discord.com/developers/applications)
2. Включите **Bot** → скопируйте токен
3. Включите intents: **Server Members**, **Message Content**
4. Пригласите бота на сервер с правами: `applications.commands`, `bot` (Send Messages, Embed Links, Manage Messages)
5. Создайте роль `BotAdmin` на сервере

### 2. Конфигурация

Скопируйте и заполните `.env`:

```env
# Discord
DISCORD_BOT_TOKEN=your_token_here
DISCORD_GUILD_ID=your_guild_id
DISCORD_ADMIN_ROLE=BotAdmin

# GitLab
GITLAB_API_URL=https://gitlab.example.com/api/v4/
GITLAB_PRIVATE_TOKEN=your_token

# Database
DATABASE_URL=postgresql+psycopg2://bot_user:bot_password@localhost:5433/bot_db

# Allure
ALLURE_REPORT_URL=http://allure.example.com/ui/

# Camera Manager
CAMERA_MANAGE_API_URL=http://camera-manager.example.com

# Test IT
TESTIT_API_URL=http://testit.example.com
TESTIT_API_KEY=your_key
TESTIT_WEBHOOK_SECRET=your_secret
WEBHOOK_PORT=8000
```

Обновите `config.json` — проекты, параметры БД, интервалы задач.

### 3. Запуск через Docker (рекомендуется)

```bash
cd Bot
docker-compose up --build -d
```

Сервисы:
- `discord-bot` — бот + FastAPI webhook (порт 8000)
- `bot-postgres` — PostgreSQL 15 (порт 5433)

### 4. Запуск локально

```bash
cd Bot
pip install -r requirements.txt
# Применить миграции
alembic upgrade head
# Запуск
python discord_bot.py
```

### 5. Миграции БД

```bash
cd Bot
alembic upgrade head        # Применить все миграции
alembic downgrade -1        # Откатить последнюю
alembic history             # Посмотреть историю
```

---

## Типы подписок

Пользователи могут подписаться на уведомления из трёх контекстов:

| Контекст | Как работает |
|----------|--------------|
| **DM** | Бот отправляет в личные сообщения |
| **Канал** | Бот пишет в канал, где была выполнена подписка |
| **Тред** | Бот пишет в тред канала |

Типы уведомлений:
- `pipeline` — пайплайны проекта
- `mr` — merge requests проекта
- `camera_status` — изменения статусов камер
- `camera_new` — новые камеры
- `camera_transfer` — трансферы камер
- `testit_case` — события Test IT

---

## Embed-стиль

| Статус | Цвет | Эмодзи |
|--------|------|--------|
| success | 🟢 Green | ✅ |
| failed | 🔴 Red | ❌ |
| running | 🔵 Blue | 🔄 |
| pending | 🟡 Yellow | ⏳ |
| info | 🟣 Blurple | ℹ️ |

---

## Test IT Webhook

Бот запускает FastAPI-сервер на порту 8000 для приёма вебхуков Test IT.

**Endpoint:** `POST /testit-webhook`

**Заголовки:**
- `x-testit-secret` — секрет для аутентификации

**Обрабатываемые события:**
- `CREATED` — создание тест-кейса/чек-листа
- `UPDATED` — изменение
- `DELETED` — удаление
- `ARCHIVED` — архивация
- `RESTORED` — восстановление

---

## Стек технологий

| Компонент | Технология |
|-----------|------------|
| Бот | discord.py >= 2.3 |
| HTTP API | httpx, requests |
| Webhook | FastAPI + uvicorn |
| База данных | PostgreSQL 15 + asyncpg |
| ORM/миграции | SQLAlchemy 2.0 + Alembic |
| Контейнеризация | Docker, docker-compose |
| Python | 3.13+ |

---

## Структура БД

```
white_list              — Управление доступом (user_id, role, status)
subscribers             — Подписки (user_id, project_id, notification_type, channel_id, thread_id)
pipeline_states         — Состояния пайплайнов (pipeline_id, status, stand, allure_report_url)
last_mrs                — Последние статусы MR (project_id, mr_iid, current_status)
camera_statuses         — Статусы камер (sn, is_alive_vcfront, is_active_agent, ...)
camera_transfer_tasks   — Задачи трансферов (sn, from_account_id, to_account_id, status)
camera_discrepancy_events — Расхождения камер (sn, type, category, summary)
testit_events           — События Test IT (author, event_type, section, name)
testit_participants     — Участники Test IT (author, is_active, include_updated)
testit_config           — Конфигурация (scoring_period, weights)
scheduled_tasks         — Расписание задач (name, next_execute_at)
last_discrepancy_check  — Последняя проверка расхождений (last_id)
```
