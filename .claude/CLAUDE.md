# GitLab Discord Bot — Миграция Telegram → Discord

## Концепция

Миграция GitLab-бота с платформы Telegram (`python-telegram-bot==21.0` + FastAPI) на Discord (`discord.py>=2.3`). Бот мониторит пайплайны, MR, камеры, Test IT статистику, управляет подписками и админ-панелью.

**Ключевой принцип:** бизнес-логика (БД, GitLab API, камеры, TestIT) сохраняется без изменений. Переписывается только транспортный слой: точка входа, обработчики команд, UI-компоненты, форматирование сообщений, фоновые задачи.

## Архитектура

```
БЫЛО (Telegram)                    СТАЛО (Discord)
─────────────────                  ─────────────────
telegram_bot.py                 →  discord_bot.py          (точка входа)
handlers.py                     →  cogs/*.py               (slash-команды)
menus.py                        →  views/*.py              (discord.ui.View/Button/Select)
format_messages.py              →  embeds.py               (discord.Embed)
jobs.py                         →  tasks/*.py              (discord.ext.tasks)
config_loader.py                →  config_loader.py        (адаптация токенов)
models.py                       →  models.py               (subscribers: chat_id→channel_id)
```

### Без изменений
- `db_operations.py` — asyncpg, универсален
- `gitlab_api.py` — httpx-клиенты
- `scheduler.py` — чистая логика БД
- `helpers/testit_event_service.py` — бизнес-логика

## Целевая структура

```
Bot/
├── discord_bot.py              # Точка входа
├── config_loader.py            # +DISCORD_BOT_TOKEN, +GUILD_ID, -TELEGRAM
├── db_operations.py            # Без изменений
├── gitlab_api.py               # Без изменений
├── models.py                   # subscribers: chat_id→channel_id, +guild_id
├── scheduler.py                # Без изменений
├── utils.py                    # Очистка от Telegram-хелперов
├── embeds.py                   # НОВЫЙ: discord.Embed форматирование
├── cogs/                       # НОВОЕ: модули slash-команд
│   ├── __init__.py
│   ├── general.py              # /start, /help, /request_access
│   ├── subscriptions.py        # /subscribe
│   ├── pipelines.py            # /pipelines
│   ├── admin.py                # /admin (по роли)
│   └── testit.py               # TestIT настройки
├── views/                      # НОВОЕ: Discord UI компоненты
│   ├── __init__.py
│   ├── main_menu.py            # Главное меню
│   ├── subscription_views.py   # Кнопки подписок
│   ├── pipeline_views.py       # Кнопки пайплайнов
│   ├── admin_views.py          # Кнопки админки
│   └── testit_views.py         # Кнопки TestIT
├── tasks/                      # НОВОЕ: фоновые задачи
│   ├── __init__.py
│   ├── pipeline_checker.py     # check_new_pipelines, check_new_mrs
│   ├── camera_checker.py       # check_camera_statuses, transfers, discrepancies
│   └── stats_sender.py         # send_daily_testit_stats
├── helpers/
│   └── testit_event_service.py # Без изменений
├── testit_webhook.py           # FastAPI → Discord (shared bot instance)
├── webhook_main.py             # Без изменений
├── requirements.txt            # discord.py>=2.3, убрать python-telegram-bot
├── config.json                 # +discord_bot_token, +guild_id
├── .env                        # Обновлённые переменные
├── alembic/                    # +миграция для subscribers
├── Dockerfile
└── docker-compose.yml
```

## Ключевые различия платформ

| Аспект | Telegram | Discord |
|--------|----------|---------|
| Команды | `/start`, `/request_access` | Slash-команды с autocomplete |
| Кнопки | InlineKeyboardButton (64 байт) | discord.ui.Button (100 символов custom_id) |
| Списки | Нет нативных | discord.ui.Select (до 25 вариантов) |
| Модалки | Нет | discord.ui.Modal (текстовый ввод) |
| Формат | Markdown/HTML строки | Embed (карточки с полями, цветами) |
| Треды | message_thread_id | Thread объект в канале |
| Планировщик | job_queue (встроен) | discord.ext.tasks |
| Доступ | white_list в БД | Роли Discord + опционально БД |
| DM | chat_id = user_id | user.send() |

## Этапы миграции

| Этап | Название | Описание |
|------|----------|----------|
| 0 | Подготовка | Discord-приложение, config, requirements, Alembic миграция |
| 1 | Скелет | discord_bot.py, /start, /help, MainMenuView, загрузка cogs |
| 2 | Подписки | /subscribe, кнопки/Select проектов, запись в БД |
| 3 | Пайплайны | История, расписания, Allure-отчёты, .properties (Modal) |
| 4 | Задачи | discord.ext.tasks, embeds.py, рассылка уведомлений |
| 5 | Админка | /admin, TestIT настройки, вебхук → Discord |
| 6 | Docker | Dockerfile, docker-compose, миграция данных |
| 7 | Тестирование | Smoke test, persistent views, edge cases |

## Принципы

### Код
1. Python 3.13+, type hints обязательны
2. Docstrings и комментарии на русском
3. Названия переменных/классов/методов на английском
4. discord.py>=2.3, async/await везде
5. Persistent views: timeout=None, статичные custom_id

### Embed-стиль
- success → `discord.Color.green()`
- failed → `discord.Color.red()`
- running → `discord.Color.blue()`
- pending → `discord.Color.yellow()`
- info → `discord.Color.blurple()`

### Cogs
1. Один cog = один файл в `cogs/`, один домен (подписки, пайплайны, админка)
2. Slash-команды с описаниями на русском
3. Autocomplete для параметров (названия проектов)
4. Проверка доступа: роли Discord + white_list в БД (гибридный подход)

### Views
1. Один домен = один файл в `views/`
2. Persistent views для главного меню (timeout=None)
3. Ephemeral views для временных взаимодействий (timeout=180)
4. Ограничение: 5 кнопок в ряду, 5 рядов максимум

### Tasks
1. `@tasks.loop(seconds=N)` для периодических проверок
2. Универсальная функция `send_notifications(bot, embed, project_id, type)`
3. Graceful error handling: канал удалён, DM заблокированы

## Стиль коммитов

Префиксы: `[init]`, `[cog]`, `[view]`, `[task]`, `[embed]`, `[config]`, `[migration]`, `[docker]`, `[test]`, `[fix]`, `[refactor]`, `[docs]`

Формат:
```
[prefix] Краткое описание на русском

- Что сделано
- Какие файлы затронуты
```

## Управление задачами

- `Tasks/backlog/` — задачи к выполнению (NNN_name.md, по номеру)
- `Tasks/done/` — выполненные (перемещаются после завершения)

## Slash-команды агента

| Команда | Назначение |
|---------|------------|
| `/start` | Актуализировать контекст, показать статус проекта |
| `/task` | Взять задачу из backlog, выполнить |
| `/push` | Тесты → коммит → push |
| `/status` | Показать состояние миграции |
| `/test` | Запустить проверки |
| `/deploy` | Docker build + запуск |

## Технический стек

- Python 3.13+, discord.py>=2.3, asyncpg, httpx, SQLAlchemy 2.0, alembic
- FastAPI + uvicorn (вебхук TestIT)
- Docker, docker-compose
- PostgreSQL
