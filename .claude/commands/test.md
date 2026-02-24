Проверить работоспособность бота.

1. Проверь синтаксис всех Python-файлов:
   ```bash
   cd Bot
   python -m py_compile discord_bot.py 2>&1
   python -m py_compile embeds.py 2>&1
   for f in cogs/*.py views/*.py tasks/*.py; do
     [ -f "$f" ] && python -m py_compile "$f" 2>&1
   done
   ```

2. Проверь импорты:
   ```bash
   python -c "
   import discord
   from discord.ext import commands, tasks
   print(f'discord.py {discord.__version__}')
   " 2>&1
   ```

3. Проверь структуру cogs (если существуют):
   ```bash
   python -c "
   import importlib, sys
   sys.path.insert(0, '.')
   for mod in ['cogs.general', 'cogs.subscriptions', 'cogs.pipelines', 'cogs.admin', 'cogs.testit']:
       try:
           importlib.import_module(mod)
           print(f'  ✅ {mod}')
       except Exception as e:
           print(f'  ❌ {mod}: {e}')
   " 2>&1
   ```

4. Если есть pytest-тесты — запусти:
   ```bash
   pytest tests/ -v --tb=short 2>/dev/null || echo "Тесты не настроены"
   ```

Выведи отчёт:
```
Проверка — результат
═══════════════════
Синтаксис:  X ✅ / X ❌
Импорты:    ✅/❌
Cogs:       X ✅ / X ❌
Тесты:      X passed / X failed
```
