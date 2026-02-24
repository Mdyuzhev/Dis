# scheduler.py
import logging
from datetime import datetime, time, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


async def reschedule_daily_stats_job(conn, force_now: datetime = None) -> Optional[datetime]:
    """
    Пересчитывает next_execute_at для send_daily_testit_stats.
    Возвращает новое время выполнения (UTC).
    """
    row = await conn.fetchrow(
        "SELECT schedule_type, next_execute_at FROM scheduled_tasks WHERE name = 'send_daily_testit_stats';"
    )
    if not row:
        logger.warning("Задача send_daily_testit_stats не найдена в БД")
        return None

    msk_tz = timezone(timedelta(hours=3))
    if force_now is not None:
        if force_now.tzinfo is None:
            force_now = force_now.replace(tzinfo=timezone.utc)
        now_msk = force_now.astimezone(msk_tz)
    else:
        now_msk = datetime.now(msk_tz)

    # Целевое время: из старого next_execute_at или по умолчанию 19:00
    target_time = time(19, 0)
    if row["next_execute_at"]:
        prev_msk = row["next_execute_at"].astimezone(msk_tz)
        target_time = prev_msk.time()

    if row["schedule_type"] == "weekly":
        days_ahead = (4 - now_msk.weekday()) % 7
        if days_ahead == 0 and now_msk.time() >= target_time:
            days_ahead = 7
        next_dt = now_msk + timedelta(days=days_ahead)
    else:
        next_dt = now_msk + timedelta(days=1) if now_msk.time() >= target_time else now_msk

    next_dt = next_dt.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
    next_utc = next_dt.astimezone(timezone.utc)

    await conn.execute(
        """
        UPDATE scheduled_tasks
        SET last_execute_at = $1, next_execute_at = $2
        WHERE name = 'send_daily_testit_stats';
        """,
        now_msk.astimezone(timezone.utc),
        next_utc
    )

    logger.info(f"🔄 Расписание обновлено: {next_dt.strftime('%H:%M')} MSK → {next_utc} UTC")
    return next_utc
