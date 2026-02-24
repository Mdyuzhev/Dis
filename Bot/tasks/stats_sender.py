"""Фоновая задача: ежедневная отправка статистики Test IT."""

import logging
from datetime import datetime, time, timedelta, timezone

from discord.ext import commands, tasks

from db_operations import connect_to_db
from embeds import format_daily_testit_stats_embed, send_testit_notifications
from scheduler import reschedule_daily_stats_job

logger = logging.getLogger(__name__)

MSK_TZ = timezone(timedelta(hours=3))

# Интервал проверки — каждые 60 секунд (проверяем, наступило ли время)
CHECK_INTERVAL = 60


def get_stats_period(
    now_msk: datetime, target_time: time, period_type: str
) -> tuple[datetime, datetime]:
    """
    Возвращает (start, end) для периода статистики.
    Все даты — aware, в часовом поясе MSK.
    """
    if now_msk.time() >= target_time:
        end_msk = datetime.combine(now_msk.date(), target_time).replace(
            tzinfo=now_msk.tzinfo
        )
        if end_msk > now_msk:
            end_msk -= timedelta(days=1)
    else:
        end_msk = datetime.combine(
            (now_msk - timedelta(days=1)).date(), target_time
        ).replace(tzinfo=now_msk.tzinfo)

    if period_type == "weekly":
        start_msk = end_msk - timedelta(days=7)
    else:
        start_msk = end_msk - timedelta(days=1)

    return start_msk, end_msk


class StatsSender(commands.Cog):
    """Cog с фоновой задачей отправки статистики Test IT."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """Запуск задачи при загрузке cog."""
        self.check_stats_schedule_task.start()

    async def cog_unload(self) -> None:
        """Остановка задачи при выгрузке."""
        self.check_stats_schedule_task.cancel()

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def check_stats_schedule_task(self) -> None:
        """Проверяет, наступило ли время отправки статистики."""
        now_msk = datetime.now(MSK_TZ)

        conn = await connect_to_db()
        if not conn:
            logger.error("stats_sender: не удалось подключиться к БД")
            return

        try:
            task_row = await conn.fetchrow(
                "SELECT next_execute_at FROM scheduled_tasks "
                "WHERE name = 'send_daily_testit_stats';"
            )
            if not task_row or not task_row["next_execute_at"]:
                logger.debug("Задача send_daily_testit_stats не настроена")
                return

            next_exec_utc = task_row["next_execute_at"]
            if next_exec_utc.tzinfo is None:
                next_exec_utc = next_exec_utc.replace(tzinfo=timezone.utc)
            next_exec_msk = next_exec_utc.astimezone(MSK_TZ).replace(microsecond=0)

            if now_msk < next_exec_msk:
                return  # Ещё не время

            # Время наступило — выполняем
            await conn.execute(
                "UPDATE scheduled_tasks SET last_execute_at = $1 "
                "WHERE name = 'send_daily_testit_stats';",
                datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error(f"Ошибка проверки расписания: {e}", exc_info=True)
            return
        finally:
            await conn.close()

        await self._send_stats(now_msk, next_exec_msk)

    @check_stats_schedule_task.before_loop
    async def before_check_stats(self) -> None:
        await self.bot.wait_until_ready()

    async def _send_stats(self, now_msk: datetime, next_exec_msk: datetime) -> None:
        """Сбор и отправка статистики."""
        # Получаем scoring_period
        conn_config = await connect_to_db()
        if not conn_config:
            return

        try:
            config = await conn_config.fetchrow(
                "SELECT scoring_period FROM testit_config WHERE id = 1;"
            )
            period = (config and config["scoring_period"]) or "daily"
        except Exception as e:
            logger.error(f"Ошибка получения scoring_period: {e}")
            period = "daily"
        finally:
            await conn_config.close()

        target_time = next_exec_msk.time()
        start_msk, end_msk = get_stats_period(now_msk, target_time, period)
        start_utc_naive = start_msk.astimezone(timezone.utc).replace(tzinfo=None)
        end_utc_naive = end_msk.astimezone(timezone.utc).replace(tzinfo=None)

        logger.info(f"Сбор статистики за период: {start_msk} – {end_msk} (MSK)")

        # Собираем данные
        conn_stats = await connect_to_db()
        if not conn_stats:
            return

        try:
            weights_row = await conn_stats.fetchrow(
                "SELECT created_weight, updated_weight, deleted_weight "
                "FROM testit_config WHERE id = 1;"
            )
            created_w = (weights_row and weights_row["created_weight"]) or 1.0
            updated_w = (weights_row and weights_row["updated_weight"]) or 0.1
            deleted_w = (weights_row and weights_row["deleted_weight"]) or 0.05

            rows = await conn_stats.fetch(
                """
                SELECT
                    sub.author,
                    sub.created_score, sub.updated_score, sub.deleted_score,
                    sub.created_count, sub.updated_count, sub.deleted_count,
                    (sub.created_score + sub.updated_score + sub.deleted_score) AS total_score
                FROM (
                    SELECT
                        e.author,
                        SUM(CASE WHEN e.event_type='CREATED' THEN $1 ELSE 0 END) AS created_score,
                        SUM(CASE WHEN e.event_type='UPDATED' THEN $2 ELSE 0 END) AS updated_score,
                        SUM(CASE WHEN e.event_type='DELETED' THEN $3 ELSE 0 END) AS deleted_score,
                        COUNT(CASE WHEN e.event_type='CREATED' THEN 1 END) AS created_count,
                        COUNT(CASE WHEN e.event_type='UPDATED' THEN 1 END) AS updated_count,
                        COUNT(CASE WHEN e.event_type='DELETED' THEN 1 END) AS deleted_count
                    FROM testit_events e
                    JOIN testit_participants p ON e.author = p.author
                    WHERE p.is_active = true
                      AND e.created_at >= $4
                      AND e.created_at < $5
                    GROUP BY e.author
                ) AS sub
                ORDER BY total_score DESC;
                """,
                created_w,
                updated_w,
                deleted_w,
                start_utc_naive,
                end_utc_naive,
            )
        except Exception as e:
            logger.error(f"Ошибка сбора статистики: {e}", exc_info=True)
            return
        finally:
            await conn_stats.close()

        display_date = end_msk - timedelta(seconds=1)

        if not rows:
            embed = format_daily_testit_stats_embed(
                stats=[],
                start_date=display_date,
                winner=None,
                total_score=0.0,
                no_activity=True,
            )
        else:
            stats = []
            top_author = None
            max_score = 0.0
            for r in rows:
                score = round(r["total_score"], 2)
                stats.append(
                    {
                        "author": r["author"],
                        "created": r["created_count"],
                        "updated": r["updated_count"],
                        "deleted": r["deleted_count"],
                        "score": score,
                    }
                )
                if score > max_score:
                    max_score = score
                    top_author = r["author"]

            embed = format_daily_testit_stats_embed(
                stats=stats,
                start_date=display_date,
                winner=top_author,
                total_score=max_score,
                no_activity=False,
            )

        # Рассылка
        sent_count, first_thread_msg = await send_testit_notifications(self.bot, embed)
        logger.info(f"Статистика Test IT ({period}) отправлена {sent_count} подписчикам")

        # Закрепляем первое сообщение в треде
        if first_thread_msg:
            try:
                await first_thread_msg.pin()
            except Exception as e:
                logger.warning(f"Не удалось закрепить сообщение: {e}")

        # Перепланирование
        conn_reschedule = await connect_to_db()
        if not conn_reschedule:
            return

        try:
            next_run_utc = await reschedule_daily_stats_job(conn_reschedule, now_msk)
            if next_run_utc:
                logger.info(f"Перепланировано: следующий запуск {next_run_utc} UTC")
            else:
                logger.error("Не удалось определить следующее время выполнения")
        except Exception as e:
            logger.exception("Ошибка при перепланировании задачи")
        finally:
            await conn_reschedule.close()


async def setup(bot: commands.Bot) -> None:
    """Загрузка cog."""
    await bot.add_cog(StatsSender(bot))
