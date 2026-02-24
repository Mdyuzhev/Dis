import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def register_new_participant_if_needed(conn, author: str):
    """Регистрирует нового участника геймификации, если его нет."""
    try:
        exists = await conn.fetchval("SELECT 1 FROM testit_participants WHERE author = $1;", author)
        if not exists:
            await conn.execute(
                """
                INSERT INTO testit_participants 
                (author, is_active, include_updated, include_deleted)
                VALUES ($1, true, true, false);
                """,
                author
            )
            logger.info(f"✅ Участник добавлен автоматически: {author}")
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении участника {author}: {e}")


async def save_testit_event(conn, payload: dict, section_name: str):
    """Сохраняет событие в testit_events"""
    try:
        await conn.execute(
            """
            INSERT INTO testit_events 
            (event_type, work_item_id, work_item_type, name, author, 
             project_name, section_id, section_name, url, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, CURRENT_TIMESTAMP);
            """,
            payload.get("eventType"),
            payload.get("workItemId"),
            payload.get("workItemType"),
            payload.get("name"),
            payload.get("author"),
            payload.get("project"),
            payload.get("section"),
            section_name,
            payload.get("url")
        )
        logger.info(f"💾 Событие сохранено: {payload.get('eventType')} от {payload.get('author')}")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения события: {e}")


async def should_skip_notification_for_author(conn, author: str) -> bool:
    """Проверяет, нужно ли пропустить уведомления для автора"""
    try:
        is_active = await conn.fetchval(
            "SELECT is_active FROM testit_participants WHERE author = $1;", author
        )
        return is_active is False
    except Exception as e:
        logger.warning(f"⚠️ Не удалось проверить статус участника {author}: {e}")
        return False