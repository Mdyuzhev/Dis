# Задача 004: Фоновые задачи и уведомления

## Цель
Переключить все фоновые проверки на `discord.ext.tasks`, создать embeds.py для форматирования, реализовать рассылку.

## Зависимости
Задача 002 (подписки в БД). Задача 001 (скелет бота).

## Контекст
Прочитать **обязательно**:
- `Bot/jobs.py` — текущие фоновые задачи (check_new_pipelines, check_new_mrs, check_camera_*)
- `Bot/format_messages.py` — текущее форматирование сообщений
- `Bot/stats_handler.py` — отправка статистики Test IT

## Шаги

### 1. Создать Bot/embeds.py — форматирование уведомлений
Переписать ВСЕ функции из `format_messages.py`, возвращая `discord.Embed`:

Цвета по статусу:
- success → `discord.Color.green()`
- failed → `discord.Color.red()`
- running → `discord.Color.blue()`
- pending → `discord.Color.yellow()`

Пример трансформации:
```python
def format_pipeline_embed(pipeline_data, project_name) -> discord.Embed:
    embed = discord.Embed(
        title="▶️ Новый пайплайн запущен!",
        color=discord.Color.blue(),
        url=web_url
    )
    embed.add_field(name="Проект", value=project_name, inline=True)
    embed.add_field(name="Статус", value="🔄 В процессе", inline=True)
    embed.set_footer(text=f"Pipeline #{pipeline_id}")
    return embed
```

### 2. Универсальная функция рассылки
В embeds.py или отдельном utils-файле:
```python
async def send_notifications(bot, embed, project_id, notification_type):
    # Получить подписчиков из БД
    # Для каждого: DM → user.send(), channel → channel.send(), thread → thread.send()
    # Graceful: try/except на каждую отправку, логирование ошибок
    # Rate limit: asyncio.sleep(0.5) между отправками
```

### 3. Создать Bot/tasks/pipeline_checker.py
Перенести `check_new_pipelines` и `check_new_mrs` из `jobs.py`.
Обернуть в `@tasks.loop(seconds=300)`.
Заменить `context.bot.send_message()` → `send_notifications(bot, embed, ...)`.

### 4. Создать Bot/tasks/camera_checker.py
Перенести `check_camera_statuses`, `check_camera_transfers`, `check_camera_discrepancies`.
Аналогичная обёртка в `@tasks.loop`.

### 5. Создать Bot/tasks/stats_sender.py
Перенести `send_daily_testit_stats` из `stats_handler.py`.
Закрепление сообщения: `await message.pin()`.
Планирование: хранить в БД `next_execute_at`, в `@tasks.loop(seconds=60)` проверять время.

### 6. Запуск задач в discord_bot.py
В `on_ready` или `setup_hook` запустить все tasks:
```python
from tasks.pipeline_checker import PipelineChecker
await bot.add_cog(PipelineChecker(bot))
```

## Проверка
- Фоновые задачи запускаются при старте бота (лог)
- При изменении статуса пайплайна — уведомление приходит в нужный канал/DM
- Embed отображается с полями и цветами
- Ежедневная статистика отправляется и закрепляется
- Ошибки при отправке (удалённый канал, заблокированный DM) не крашат задачу

## Коммит
```
[task][embed] Фоновые задачи и уведомления

- embeds.py: форматирование всех уведомлений в discord.Embed
- tasks/pipeline_checker.py: пайплайны и MR
- tasks/camera_checker.py: камеры
- tasks/stats_sender.py: статистика Test IT
- Универсальная рассылка send_notifications()
```
