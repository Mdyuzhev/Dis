Коммит и push изменений.

1. Проверь статус: `git status`
2. Если есть изменения — проверь что бот запускается:
   ```bash
   cd Bot && python -c "import discord_bot" 2>/dev/null || echo "⚠️ Импорт не проходит"
   ```
3. Добавь файлы: `git add -A`
4. Покажи diff: `git diff --cached --stat`
5. Сформируй коммит с правильным префиксом из CLAUDE.md
6. Push: `git push origin $(git branch --show-current)`

## Префиксы коммитов

`[init]` `[cog]` `[view]` `[task]` `[embed]` `[config]` `[migration]` `[docker]` `[test]` `[fix]` `[refactor]` `[docs]`

## Формат

```
[prefix] Краткое описание на русском

- Что сделано
- Какие файлы затронуты
```
