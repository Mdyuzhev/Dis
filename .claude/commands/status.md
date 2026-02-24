Показать состояние миграции.

```bash
echo "=== Структура проекта ==="
find . -type f -not -path './.git/*' -not -path './__pycache__/*' -not -name '*.pyc' | sort

echo "=== Git ==="
git branch -v
git log --oneline -10
git status --short

echo "=== Telegram-файлы (старые) ==="
for f in Bot/telegram_bot.py Bot/handlers.py Bot/menus.py Bot/format_messages.py Bot/jobs.py; do
  [ -f "$f" ] && echo "  ⚠️  $f — НЕ мигрирован"
done

echo "=== Discord-файлы (новые) ==="
[ -f "Bot/discord_bot.py" ] && echo "  ✅ discord_bot.py" || echo "  ❌ discord_bot.py"
[ -f "Bot/embeds.py" ] && echo "  ✅ embeds.py" || echo "  ❌ embeds.py"

echo "=== Cogs ==="
ls Bot/cogs/*.py 2>/dev/null | grep -v __init__ | while read f; do echo "  ✅ $(basename $f)"; done
[ ! -d "Bot/cogs" ] && echo "  ❌ Директория не создана"

echo "=== Views ==="
ls Bot/views/*.py 2>/dev/null | grep -v __init__ | while read f; do echo "  ✅ $(basename $f)"; done
[ ! -d "Bot/views" ] && echo "  ❌ Директория не создана"

echo "=== Tasks ==="
ls Bot/tasks/*.py 2>/dev/null | grep -v __init__ | while read f; do echo "  ✅ $(basename $f)"; done
[ ! -d "Bot/tasks" ] && echo "  ❌ Директория не создана"

echo "=== Зависимости ==="
grep -c "discord.py" Bot/requirements.txt 2>/dev/null && echo "  ✅ discord.py в requirements" || echo "  ❌ discord.py отсутствует"
grep -c "python-telegram-bot" Bot/requirements.txt 2>/dev/null && echo "  ⚠️  python-telegram-bot ещё в requirements" || echo "  ✅ python-telegram-bot удалён"

echo "=== Backlog ==="
ls Tasks/backlog/ 2>/dev/null || echo "Пусто"
echo "=== Done ==="
ls Tasks/done/ 2>/dev/null || echo "Пусто"
```

Формат вывода:
```
GitLab Discord Bot — Status Report
═══════════════════════════════════════
Прогресс:    Этап X/7
Cogs:        X/5 (general, subscriptions, pipelines, admin, testit)
Views:       X/5 (main_menu, subscription, pipeline, admin, testit)
Tasks:       X/3 (pipeline_checker, camera_checker, stats_sender)
Embeds:      ✅/❌
Ветка:       ... (clean/dirty)
Задачи:      X в backlog / X выполнено

Telegram-файлы (к удалению):
- telegram_bot.py, handlers.py, menus.py, format_messages.py, jobs.py
```
