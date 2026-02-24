Собрать и запустить бота в Docker.

1. Проверь Dockerfile:
   ```bash
   cat Bot/Dockerfile
   ```

2. Проверь docker-compose:
   ```bash
   cat docker-compose.yml
   ```

3. Собери образ:
   ```bash
   cd Bot
   docker-compose down 2>/dev/null
   docker system prune -f
   docker-compose up --build -d
   ```

4. Проверь логи:
   ```bash
   docker-compose logs --tail=50
   ```

5. Проверь что бот подключился:
   ```bash
   docker-compose logs | grep -E "(ready|logged in|error|ERROR)" | tail -10
   ```

Выведи отчёт:
```
Deploy — результат
═══════════════════
Образ:      собран ✅/❌
Контейнер:  запущен ✅/❌
Бот:        подключён ✅/❌
Вебхук:     слушает ✅/❌
```

При ошибках — покажи лог и предложи исправление.
