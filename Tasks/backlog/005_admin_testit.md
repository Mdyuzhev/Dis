# Задача 005: Админ-панель и Test IT

## Цель
Перенести управление пользователями, запросы доступа, настройки Test IT, адаптировать вебхук.

## Зависимости
Задача 001 (скелет). Задача 004 (embeds.py для форматирования).

## Контекст
Прочитать **обязательно**:
- `Bot/handlers.py` — секции admin_panel, approve/reject, ban/unban
- `Bot/menus.py` — admin-кнопки, testit-настройки
- `Bot/testit_webhook.py` — FastAPI вебхук для Test IT событий
- `Bot/helpers/testit_event_service.py` — бизнес-логика (без изменений)

## Шаги

### 1. Создать Bot/cogs/admin.py
Slash-команда `/admin` — доступна только по роли DISCORD_ADMIN_ROLE:
```python
@app_commands.checks.has_role(DISCORD_ADMIN_ROLE)
```
Подкоманды: `/admin requests`, `/admin users`, `/admin testit`.

### 2. Создать Bot/views/admin_views.py

**AccessRequestsView** — список pending-запросов:
- Embed со списком пользователей (имя, дата запроса)
- Кнопки Approve / Reject для каждого
- При нажатии: обновление БД + DM пользователю с результатом

**UsersView** — управление пользователями:
- Список с кнопками Ban / Unban
- Пагинация если пользователей много

### 3. Создать Bot/cogs/testit.py + Bot/views/testit_views.py
Меню настроек Test IT через кнопки и Modal:
- "Участники" → toggle active (кнопки)
- "Период" → Select (daily/weekly)
- "Время отправки" → Modal (ввод ЧЧ:ММ)
- "Веса событий" → Modal (ввод числа для каждого типа)

### 4. Адаптировать Bot/testit_webhook.py
Прочитать текущий файл. Заменить `Bot(token=TELEGRAM_BOT_TOKEN)` на Discord.

Рекомендуемый подход — **shared bot instance**:
- Запускать FastAPI в том же процессе через `asyncio.create_task` в `on_ready`
- Или передать ссылку на bot-объект в FastAPI app через `app.state.bot`
- При получении вебхука: `channel = bot.get_channel(channel_id); await channel.send(embed=embed)`

Пример:
```python
# В discord_bot.py:
async def on_ready():
    from testit_webhook import create_app
    app = create_app(bot)
    config = uvicorn.Config(app, host="0.0.0.0", port=WEBHOOK_PORT)
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve())
```

## Проверка
- `/admin` доступен только пользователям с ролью
- Запросы на доступ отображаются с кнопками Approve/Reject
- Approve/Reject работают, пользователь получает DM
- Настройки Test IT изменяются через Modal
- Вебхук Test IT принимает события и отправляет в Discord

## Коммит
```
[cog][view] Админ-панель, Test IT настройки, вебхук

- cogs/admin.py: /admin с проверкой роли
- views/admin_views.py: AccessRequests, Users
- cogs/testit.py + views/testit_views.py: настройки Test IT
- testit_webhook.py: адаптация под shared bot instance
```
