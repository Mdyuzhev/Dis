"""Фоновые задачи: проверка пайплайнов и MR."""

import logging
from datetime import datetime, timedelta

from discord.ext import commands, tasks

from config_loader import FIXED_PROJECTS, JOBS_CONFIG
from db_operations import connect_to_db
from embeds import (
    format_pipeline_embed,
    add_allure_fields,
    add_test_statistics_from_db,
    format_mr_embed,
    send_notifications,
)
from gitlab_api import (
    get_pipeline_details,
    get_merge_requests,
    get_allure_report_url,
    get_allure_summary,
    get_recent_pipelines,
)
from utils import enrich_pipeline_with_allure_data, find_stand_and_schedule_id

logger = logging.getLogger(__name__)

PIPELINE_INTERVAL = int(JOBS_CONFIG.get("check_new_pipelines_interval", 300))
MR_INTERVAL = int(JOBS_CONFIG.get("check_new_mrs_interval", 300))


class PipelineChecker(commands.Cog):
    """Cog с фоновыми задачами проверки пайплайнов и MR."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """Запуск задач при загрузке cog."""
        self.check_pipelines_task.start()
        self.check_mrs_task.start()

    async def cog_unload(self) -> None:
        """Остановка задач при выгрузке."""
        self.check_pipelines_task.cancel()
        self.check_mrs_task.cancel()

    # ── Пайплайны ──────────────────────────────────────────

    @tasks.loop(seconds=PIPELINE_INTERVAL)
    async def check_pipelines_task(self) -> None:
        """Проверка новых и завершённых пайплайнов."""
        conn = await connect_to_db()
        if not conn:
            logger.error("check_pipelines: не удалось подключиться к БД")
            return

        try:
            for project_id in FIXED_PROJECTS:
                last_row = await conn.fetchrow(
                    "SELECT MAX(updated_at) FROM pipeline_states WHERE project_id = $1",
                    project_id,
                )
                since_time = (
                    (last_row[0] - timedelta(minutes=2))
                    if last_row and last_row[0]
                    else None
                )

                pipelines_list = await get_recent_pipelines(
                    project_id, updated_after=since_time
                )
                if not pipelines_list:
                    continue

                for pipeline in pipelines_list:
                    pid = pipeline["id"]
                    status = pipeline["status"]

                    existing = await conn.fetchrow(
                        "SELECT status, is_notified_start, is_completed "
                        "FROM pipeline_states WHERE pipeline_id = $1",
                        pid,
                    )

                    if existing and existing["status"] == status:
                        continue

                    details = await get_pipeline_details(project_id, pid)
                    if not details:
                        logger.warning(f"Пропускаем пайплайн {pid}: нет деталей")
                        continue

                    try:
                        created_at_str = details.get("created_at")
                        if created_at_str:
                            created_at = datetime.fromisoformat(
                                created_at_str.replace("Z", "+00:00")
                            )
                        else:
                            created_at = datetime.utcnow()
                    except Exception:
                        created_at = datetime.utcnow()

                    stand_value, schedule_id = await find_stand_and_schedule_id(
                        project_id, pid
                    )
                    if not stand_value:
                        commit_msg = (
                            (details.get("commit", {}) or {})
                            .get("message", "")
                            .lower()
                        )
                        stand_value = next(
                            (
                                k
                                for k, v in [
                                    ("p1", "p1"),
                                    ("staging", "staging"),
                                    ("stage", "staging"),
                                    ("demo", "demo"),
                                    ("prod", "prod"),
                                ]
                                if v in commit_msg
                            ),
                            "manual",
                        )

                    user_data = details.get("user") or {}
                    author_name = user_data.get("name") or "Неизвестно"

                    if existing:
                        await conn.execute(
                            "UPDATE pipeline_states SET status = $1, "
                            "updated_at = CURRENT_TIMESTAMP WHERE pipeline_id = $2",
                            status,
                            pid,
                        )

                        if (
                            status in ("success", "failed")
                            and not existing["is_completed"]
                        ):
                            await self._notify_pipeline_finished(
                                conn, pid, project_id, stand_value
                            )
                            await conn.execute(
                                "UPDATE pipeline_states SET is_completed = TRUE "
                                "WHERE pipeline_id = $1",
                                pid,
                            )
                    else:
                        await conn.execute(
                            """INSERT INTO pipeline_states
                            (pipeline_id, project_id, status, ref, web_url,
                             author_name, created_at, updated_at, stand, schedule_id)
                            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
                            pid,
                            project_id,
                            status,
                            details["ref"],
                            details["web_url"],
                            author_name,
                            created_at,
                            created_at,
                            stand_value,
                            schedule_id,
                        )

                        if status == "running":
                            await self._notify_pipeline_started(
                                conn, pid, project_id, stand_value
                            )

        except Exception as e:
            logger.error(f"Ошибка в check_pipelines: {e}", exc_info=True)
        finally:
            await conn.close()

    @check_pipelines_task.before_loop
    async def before_check_pipelines(self) -> None:
        await self.bot.wait_until_ready()

    async def _notify_pipeline_started(
        self, conn, pid: int, project_id: str, stand_value: str
    ) -> None:
        """Уведомление о запуске пайплайна."""
        row = await conn.fetchrow(
            "SELECT * FROM pipeline_states WHERE pipeline_id = $1", pid
        )
        if row["is_notified_start"]:
            return

        embed = format_pipeline_embed(
            project_id=project_id,
            project_name=FIXED_PROJECTS[project_id],
            stand_value=stand_value,
            pipeline_id=row["pipeline_id"],
            ref=row["ref"],
            status=row["status"],
            author_name=row["author_name"],
            web_url=row["web_url"],
            event_type="start",
        )

        await send_notifications(self.bot, embed, project_id, "pipeline")
        await conn.execute(
            "UPDATE pipeline_states SET is_notified_start = TRUE WHERE pipeline_id = $1",
            pid,
        )

    async def _notify_pipeline_finished(
        self, conn, pid: int, project_id: str, stand_value: str
    ) -> None:
        """Уведомление о завершении пайплайна."""
        row = await conn.fetchrow(
            "SELECT * FROM pipeline_states WHERE pipeline_id = $1", pid
        )

        embed = format_pipeline_embed(
            project_id=project_id,
            project_name=FIXED_PROJECTS[project_id],
            stand_value=stand_value,
            pipeline_id=row["pipeline_id"],
            ref=row["ref"],
            status=row["status"],
            author_name=row["author_name"],
            web_url=row["web_url"],
            event_type="finish",
        )

        # Обогащаем Allure-данными
        analysis = await enrich_pipeline_with_allure_data(
            get_allure_report_url,
            get_allure_summary,
            conn,
            project_id,
            pid,
            row,
        )

        if analysis["stats"]:
            embed = add_allure_fields(
                embed,
                analysis["allure_url"],
                analysis["stats"],
                analysis["time_stats"],
            )
        elif row["tests_passed"] is not None and row["tests_failed"] is not None:
            embed = add_allure_fields(embed, analysis["allure_url"], None, None)
            embed = add_test_statistics_from_db(
                embed,
                row["tests_passed"],
                row["tests_failed"],
                row["duration_sec"],
            )
        else:
            embed = add_allure_fields(embed, analysis["allure_url"], None, None)

        await send_notifications(self.bot, embed, project_id, "pipeline")

    # ── Merge Requests ─────────────────────────────────────

    @tasks.loop(seconds=MR_INTERVAL)
    async def check_mrs_task(self) -> None:
        """Проверка новых и изменённых MR."""
        conn = await connect_to_db()
        if not conn:
            logger.error("check_mrs: не удалось подключиться к БД")
            return

        try:
            for project_id in FIXED_PROJECTS:
                merge_requests = await get_merge_requests(project_id)
                if not merge_requests:
                    continue

                for mr in merge_requests:
                    mr_iid = mr["iid"]
                    mr_status = mr["state"]

                    existing_mr = await conn.fetchrow(
                        "SELECT current_status FROM last_mrs "
                        "WHERE project_id = $1 AND mr_iid = $2;",
                        project_id,
                        mr_iid,
                    )

                    if existing_mr:
                        previous_status = existing_mr["current_status"]
                        if previous_status != mr_status:
                            await conn.execute(
                                "UPDATE last_mrs SET current_status = $1 "
                                "WHERE project_id = $2 AND mr_iid = $3;",
                                mr_status,
                                project_id,
                                mr_iid,
                            )

                            embed = format_mr_embed(
                                project_name=FIXED_PROJECTS[project_id],
                                mr_iid=mr_iid,
                                title=mr["title"],
                                author_name=mr["author"]["name"],
                                source_branch=mr["source_branch"],
                                target_branch=mr["target_branch"],
                                web_url=mr["web_url"],
                                status=mr_status,
                                is_new=False,
                            )
                            await send_notifications(
                                self.bot, embed, project_id, "mr"
                            )
                    else:
                        await conn.execute(
                            "INSERT INTO last_mrs (project_id, mr_iid, current_status) "
                            "VALUES ($1, $2, $3);",
                            project_id,
                            mr_iid,
                            mr_status,
                        )

                        embed = format_mr_embed(
                            project_name=FIXED_PROJECTS[project_id],
                            mr_iid=mr_iid,
                            title=mr["title"],
                            author_name=mr["author"]["name"],
                            source_branch=mr["source_branch"],
                            target_branch=mr["target_branch"],
                            web_url=mr["web_url"],
                            status=mr_status,
                            is_new=True,
                        )
                        await send_notifications(self.bot, embed, project_id, "mr")
        except Exception as e:
            logger.error(f"Ошибка в check_mrs: {e}", exc_info=True)
        finally:
            await conn.close()

    @check_mrs_task.before_loop
    async def before_check_mrs(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    """Загрузка cog."""
    await bot.add_cog(PipelineChecker(bot))
