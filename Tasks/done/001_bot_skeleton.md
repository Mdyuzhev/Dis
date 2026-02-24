# Задача 001: Скелет бота и базовые команды

## Цель
Бот запускается, подключается к Discord, отвечает на /start и /help, показывает главное меню.

## Зависимости
Задача 000 выполнена (config, requirements, директории).

## Шаги

### 1. Создать Bot/discord_bot.py — точка входа
Прочитать `Bot/telegram_bot.py` для понимания текущей логики запуска.

Создать `discord_bot.py`:
- Инициализация `commands.Bot` с intents (guilds, guild_messages, message_content, dm_messages)
- `setup_hook`: загрузка cogs через `bot.load_extension('cogs.general')`
- `on_ready`: синхронизация slash-команд для guild, лог "Бот подключён"
- Корректный shutdown: закрытие httpx-клиентов из gitlab_api
- Запуск: `bot.run(DISCORD_BOT_TOKEN)`

### 2. Создать Bot/cogs/general.py — базовые команды
Slash-команда `/start`:
- Проверка доступа (гибридный: роль Discord + white_list в БД)
- Если доступ есть — показать MainMenuView
- Если нет — предложить `/request_access`

Slash-команда `/help`:
- Список доступных команд и проектов в Embed

Slash-команда `/request_access`:
- Создаёт запрос в БД (pending)
- Отправляет Embed в admin-канал с кнопками Approve/Reject

### 3. Создать Bot/views/main_menu.py — главное меню
Класс `MainMenuView(discord.ui.View)` с timeout=None (persistent):
- Кнопка "📋 Подписки" (custom_id="main:subscription")
- Кнопка "🔧 Пайплайны" (custom_id="main:pipelines")  
- Кнопка "ℹ️ Справка" (custom_id="main:help")
- Кнопка "⚙️ Админ" (custom_id="main:admin") — условно, по роли

Каждая кнопка — callback с `interaction.response.edit_message()`.

### 4. Регистрация persistent views
В `setup_hook` добавить `bot.add_view(MainMenuView())` для работы после перезапуска.

## Проверка
- Бот запускается и подключается к серверу (`on_ready` срабатывает)
- Slash-команды /start и /help видны в списке Discord
- /start показывает Embed с кнопками главного меню
- Кнопки реагируют на нажатие
- Логи показывают загрузку cogs

## Коммит
```
[init] Скелет Discord-бота: точка входа, /start, /help, главное меню

- discord_bot.py: инициализация, загрузка cogs, shutdown
- cogs/general.py: /start, /help, /request_access
- views/main_menu.py: MainMenuView с persistent кнопками
```
