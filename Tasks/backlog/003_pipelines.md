# Задача 003: Пайплайны и расписания

## Цель
Просмотр истории пайплайнов, расписаний, Allure-отчётов, редактирование .properties через Discord.

## Зависимости
Задача 001 выполнена (скелет). Задача 002 желательна но не обязательна.

## Контекст
Прочитать **обязательно**:
- `Bot/handlers.py` — текущая логика пайплайнов (pipeline_history, schedules, allure)
- `Bot/menus.py` — inline-кнопки для навигации
- `Bot/property_editor.py` — редактор .properties файлов
- `Bot/gitlab_api.py` — API-вызовы (get_pipelines, get_schedules, trigger_schedule)

## Шаги

### 1. Создать Bot/cogs/pipelines.py
Slash-команда `/pipelines` — показывает список проектов для выбора.
Использовать autocomplete для названий проектов:
```python
@pipelines.autocomplete('project')
async def project_autocomplete(interaction, current):
    # Возвращать проекты из config, фильтруя по current
```

Подкоманды (опционально): `/pipelines history`, `/pipelines schedules`, `/pipelines reports`.

### 2. Создать Bot/views/pipeline_views.py

**PipelineOptionsView** — кнопки после выбора проекта:
- "📊 Отчёты" → AllureReportsView
- "📜 История" → PipelineHistoryEmbed
- "⏰ Расписания" → SchedulesView
- "📝 Файлы .properties" → PropertiesView
- "← Назад"

**PipelineHistoryEmbed** — 3 последних пайплайна в Embed:
- Поля: status (emoji), ID, branch, время, автор
- Кнопка "Обновить"

**SchedulesView** — список расписаний с кнопками:
- "👁 Просмотр" — детали расписания
- "▶️ Запустить" — с двойным подтверждением (кнопка "Подтвердить запуск?")
- Вызов `gitlab_api.trigger_schedule()`

**AllureReportsView** — пагинация с ◀️/▶️:
- Embed с таблицей отчётов (название, статус, дата)
- По 5 отчётов на страницу

### 3. Редактор .properties через Modal
Прочитать `Bot/property_editor.py`.
Кнопка "Редактировать" → `discord.ui.Modal`:
- TextInput с текущим содержимым (label="Содержимое .properties")
- Ограничение Modal: 4000 символов
- После подтверждения — показать diff в Embed + кнопка "Сохранить"
- При длинных файлах: формат "ключ=значение" для частичного обновления

## Проверка
- /pipelines показывает список проектов с autocomplete
- История загружается из GitLab API, отображается в Embed
- Расписания отображаются с кнопками запуска
- Запуск расписания требует подтверждения и работает
- Allure-отчёты с пагинацией
- Редактор .properties открывает Modal, сохраняет изменения

## Коммит
```
[cog][view] Пайплайны: история, расписания, Allure-отчёты, .properties

- cogs/pipelines.py: /pipelines с autocomplete
- views/pipeline_views.py: History, Schedules, AllureReports, Properties
- Modal для редактирования .properties
```
