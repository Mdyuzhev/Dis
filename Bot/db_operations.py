# db_operations.py

import asyncpg

from config_loader import DB_CONFIG


async def connect_to_db():
    """Подключение к базе данных."""
    try:
        return await asyncpg.connect(
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"]
        )
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        return None
