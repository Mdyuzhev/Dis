# Задача 002: Система подписок

## Цель
Пользователи подписываются/отписываются на уведомления через Discord UI.

## Зависимости
Задача 001 выполнена (скелет бота, MainMenuView).

## Контекст
Прочитать **обязательно**:
- `Bot/handlers.py` — текущая логика подписок (subscribe/unsubscribe)
- `Bot/menus.py` — текущие inline-кнопки Telegram
- `Bot/db_operations.py` — SQL-запросы подписок

## Шаги

### 1. Создать Bot/cogs/subscriptions.py
Slash-команда `/subscribe` → открывает SubscriptionMenuView.
Альтернативно: кнопка "Подписки" из MainMenuView вызывает тот же view.

### 2. Создать Bot/views/subscription_views.py

**SubscriptionMenuView** — выбор проекта:
- Вариант A: 6 кнопок (по одной на проект) + "Камеры" + "Test IT" + "Назад"
- Вариант B: `discord.ui.Select` (выпадающий список проектов) — компактнее
- Рекомендация: Select для проектов, кнопки для камер/TestIT

**ProjectSubscriptionView** — для выбранного проекта:
- Кнопка "Подписаться на пайплайны" / "Отписаться"
- Кнопка "Подписаться на MR" / "Отписаться"
- Кнопка "Назад"
- Состояние кнопок зависит от текущих подписок пользователя (запрос в БД)

### 3. Адаптировать логику подписок
Определение контекста при подписке:
- Команда в DM → `source_type='dm'`, `channel_id=NULL`
- Команда в канале → `source_type='channel'`, `channel_id=interaction.channel_id`
- Команда в треде → `source_type='thread'`, `channel_id=parent_id`, `thread_id=channel_id`

SQL INSERT/DELETE перенести из `handlers.py` с заменой полей (chat_id→channel_id и т.д.).

## Проверка
- Пользователь подписывается на пайплайны проекта из DM и из канала
- Подписки сохраняются в БД с корректным source_type
- Отписка удаляет запись
- Повторная подписка не создаёт дубликатов (ON CONFLICT DO NOTHING)
- Кнопки отражают текущее состояние подписки

## Коммит
```
[cog][view] Система подписок: выбор проектов, подписка/отписка

- cogs/subscriptions.py: /subscribe
- views/subscription_views.py: SubscriptionMenuView, ProjectSubscriptionView
- Адаптация SQL для Discord (channel_id, source_type)
```
