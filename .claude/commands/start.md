Актуализируй контекст перед началом работы.

1. Прочитай `.claude/CLAUDE.md` — основной контекст проекта
2. Посмотри текущую структуру:
   ```bash
   find . -type f -not -path './.git/*' -not -path './__pycache__/*' -not -name '*.pyc' | sort
   ```
3. Git-статус:
   ```bash
   git status && git log --oneline -5
   ```
4. Текущие файлы бота:
   ```bash
   ls -la Bot/*.py Bot/cogs/ Bot/views/ Bot/tasks/ 2>/dev/null
   ```
5. Зависимости:
   ```bash
   cat Bot/requirements.txt
   ```
6. Задачи:
   ```bash
   ls Tasks/backlog/ Tasks/done/ 2>/dev/null
   ```
7. Конфигурация:
   ```bash
   cat Bot/.env | grep -E '^(DISCORD|TELEGRAM|DATABASE)' 2>/dev/null
   ```

Выведи краткий отчёт:
```
GitLab Discord Bot — статус миграции
═══════════════════════════════════════
Этап:         X из 7
Telegram:     X файлов осталось
Discord:      X файлов создано
  - cogs:     X
  - views:    X
  - tasks:    X
Ветка:        ...
Последний коммит: ...
Задач в backlog: X
Задач выполнено: X
```

НЕ создавай файлы. НЕ меняй код. Только читай и отчитывайся.
