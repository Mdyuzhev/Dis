"""Фоновые задачи: проверка статусов камер, трансферов, расхождений."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from discord.ext import commands, tasks

from config_loader import JOBS_CONFIG
from db_operations import connect_to_db
from embeds import (
    format_camera_status_embed,
    format_new_camera_embed,
    format_transfer_started_embed,
    format_transfer_completed_embed,
    format_transfer_failed_embed,
    format_camera_discrepancy_embed,
    send_camera_notifications,
)
from gitlab_api import (
    get_all_cameras_status,
    get_all_transfer_tasks_for_sn,
    get_account_info,
    get_camera_discrepancies,
)

logger = logging.getLogger(__name__)

CAMERA_INTERVAL = int(JOBS_CONFIG.get("check_camera_statuses_interval", 300))
DISCREPANCY_INTERVAL = int(JOBS_CONFIG.get("check_camera_discrepancies_interval", 300))

# Кэш аккаунтов для трансферов
_ACCOUNT_CACHE: Dict[int, dict] = {}


async def _get_account_info_cached(account_id: int) -> Optional[dict]:
    """Получение данных аккаунта с кэшированием."""
    account_id = int(account_id)
    if account_id in _ACCOUNT_CACHE:
        return _ACCOUNT_CACHE[account_id]

    result = await get_account_info(account_id)
    if result.get("status") == "ok":
        account_data = result["data"]
        _ACCOUNT_CACHE[account_id] = account_data
        return account_data

    logger.warning(f"Не удалось получить аккаунт {account_id}")
    return None


class CameraChecker(commands.Cog):
    """Cog с фоновыми задачами проверки камер."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """Запуск задач при загрузке cog."""
        self.check_camera_statuses_task.start()
        self.check_camera_transfers_task.start()
        self.check_camera_discrepancies_task.start()

    async def cog_unload(self) -> None:
        """Остановка задач при выгрузке."""
        self.check_camera_statuses_task.cancel()
        self.check_camera_transfers_task.cancel()
        self.check_camera_discrepancies_task.cancel()

    # ── Статусы камер ──────────────────────────────────────

    @tasks.loop(seconds=CAMERA_INTERVAL)
    async def check_camera_statuses_task(self) -> None:
        """Проверка статусов камер: онлайн/оффлайн, новые камеры."""
        conn = await connect_to_db()
        if not conn:
            logger.error("check_camera_statuses: не удалось подключиться к БД")
            return

        try:
            camera_data = await get_all_cameras_status()
            if "error" in camera_data:
                logger.error(f"Ошибка получения статусов камер: {camera_data['error']}")
                return
            if camera_data.get("status") != "ok":
                logger.error("API камер вернул некорректный статус")
                return

            accounts_data = camera_data.get("data", {}).get("accounts", {})

            for account_id_str, info in accounts_data.items():
                email = info.get("email", "")
                env = info.get("env", "")
                for cam in info.get("cameras", []):
                    sn = cam.get("sn")
                    if not sn:
                        continue

                    is_alive = cam.get("is_alive_vcfront")
                    is_active_agent = cam.get("is_active_agent")
                    is_online_agent = cam.get("is_online_agent")
                    is_active_vuf = cam.get("is_active_vuf")

                    existing = await conn.fetchrow(
                        "SELECT is_alive_vcfront, is_active_agent, is_online_agent, "
                        "is_active_vuf FROM camera_statuses WHERE sn = $1;",
                        sn,
                    )

                    if existing:
                        prev_alive = existing["is_alive_vcfront"]
                        prev_active = existing["is_active_agent"]
                        prev_online = existing["is_online_agent"]
                        prev_vuf = existing["is_active_vuf"]

                        has_significant_change = (
                            prev_alive != is_alive
                            or prev_active != is_active_agent
                            or prev_online != is_online_agent
                        )

                        if not has_significant_change and prev_vuf != is_active_vuf:
                            await conn.execute(
                                "UPDATE camera_statuses SET is_active_vuf = $1 WHERE sn = $2;",
                                is_active_vuf,
                                sn,
                            )
                            continue

                        if has_significant_change:
                            await conn.execute(
                                """UPDATE camera_statuses SET
                                    is_alive_vcfront = $1, is_active_agent = $2,
                                    is_online_agent = $3, is_active_vuf = $4,
                                    account_email = $5, account_env = $6
                                WHERE sn = $7;""",
                                is_alive,
                                is_active_agent,
                                is_online_agent,
                                is_active_vuf,
                                email,
                                env,
                                sn,
                            )

                            changes = []
                            if prev_active != is_active_agent:
                                changes.append(
                                    f"AV-Active: {'🟢' if is_active_agent else '🔴'}"
                                )
                            if prev_online != is_online_agent:
                                changes.append(
                                    f"AV-Online: {'🟢' if is_online_agent else '🔴'}"
                                )
                            if prev_alive != is_alive:
                                changes.append(
                                    f"VCF-Online: {'🟢' if is_alive else '🔴'}"
                                )

                            embed = format_camera_status_embed(
                                sn=sn,
                                email=email,
                                env=env,
                                changes=changes,
                                is_alive_vcfront=is_alive,
                                is_active_agent=is_active_agent,
                                is_online_agent=is_online_agent,
                                is_active_vuf=is_active_vuf,
                            )
                            await send_camera_notifications(
                                self.bot, embed, "camera_status"
                            )
                    else:
                        # Новая камера
                        await conn.execute(
                            """INSERT INTO camera_statuses
                               (sn, is_alive_vcfront, is_active_agent, is_online_agent,
                                is_active_vuf, account_email, account_env)
                               VALUES ($1, $2, $3, $4, $5, $6, $7);""",
                            sn,
                            is_alive,
                            is_active_agent,
                            is_online_agent,
                            is_active_vuf,
                            email,
                            env,
                        )
                        embed = format_new_camera_embed(
                            sn, email, env, is_alive, is_active_agent,
                            is_online_agent, is_active_vuf,
                        )
                        await send_camera_notifications(
                            self.bot, embed, "camera_new"
                        )

        except Exception as e:
            logger.error(f"Ошибка в check_camera_statuses: {e}", exc_info=True)
        finally:
            await conn.close()

    @check_camera_statuses_task.before_loop
    async def before_camera_statuses(self) -> None:
        await self.bot.wait_until_ready()

    # ── Трансферы камер ────────────────────────────────────

    @tasks.loop(seconds=CAMERA_INTERVAL)
    async def check_camera_transfers_task(self) -> None:
        """Проверка новых и изменённых трансферов камер."""
        conn = await connect_to_db()
        if not conn:
            logger.error("check_camera_transfers: не удалось подключиться к БД")
            return

        try:
            db_sns_query = await conn.fetch(
                "SELECT DISTINCT sn FROM camera_statuses;"
            )
            db_sns = {row["sn"] for row in db_sns_query}

            cameras_data = await get_all_cameras_status()
            api_sns: set[str] = set()
            if cameras_data.get("status") == "ok":
                accounts_data = cameras_data.get("data", {}).get("accounts", {})
                for acc in accounts_data.values():
                    for cam in acc.get("cameras", []):
                        sn = cam.get("sn")
                        if sn:
                            api_sns.add(sn)

            all_sns = db_sns | api_sns

            for sn in all_sns:
                tasks_data = await get_all_transfer_tasks_for_sn(sn)
                if "error" in tasks_data or tasks_data.get("status") != "ok":
                    continue

                for task in tasks_data["data"]["tasks"]:
                    task_id = task["id"]
                    from_acc_id = task["from_account_id"]
                    to_acc_id = task["to_account_id"]
                    target_env = task["target_env"]
                    status = task["status"]

                    try:
                        created_at = datetime.fromisoformat(
                            task["created_at"].replace("Z", "+00:00")
                        )
                        updated_at = datetime.fromisoformat(
                            task["updated_at"].replace("Z", "+00:00")
                        )
                    except ValueError as e:
                        logger.warning(f"Ошибка парсинга времени задачи {task_id}: {e}")
                        continue

                    error_msg = task.get("error")

                    existing = await conn.fetchrow(
                        "SELECT task_status FROM camera_transfer_tasks WHERE id = $1;",
                        task_id,
                    )

                    from_acc_info = await _get_account_info_cached(from_acc_id)
                    to_acc_info = await _get_account_info_cached(to_acc_id)

                    from_email = (
                        from_acc_info["email"]
                        if from_acc_info
                        else f"id={from_acc_id}"
                    )
                    to_email = (
                        to_acc_info["email"] if to_acc_info else f"id={to_acc_id}"
                    )
                    from_env = from_acc_info["env"] if from_acc_info else None
                    to_env = to_acc_info["env"] if to_acc_info else None

                    if existing:
                        prev_status = existing["task_status"]
                        if prev_status != status:
                            await conn.execute(
                                "UPDATE camera_transfer_tasks "
                                "SET task_status=$1, updated_at=$2, error_message=$3 "
                                "WHERE id=$4;",
                                status,
                                updated_at,
                                error_msg,
                                task_id,
                            )

                            if status == "completed":
                                embed = format_transfer_completed_embed(
                                    sn=sn,
                                    from_email=from_email,
                                    to_email=to_email,
                                    target_env=target_env,
                                    from_env=from_env,
                                    to_env=to_env,
                                )
                                await send_camera_notifications(
                                    self.bot, embed, "camera_transfer_completed"
                                )
                            elif status == "failed":
                                embed = format_transfer_failed_embed(
                                    sn=sn,
                                    from_email=from_email,
                                    to_email=to_email,
                                    error=error_msg,
                                    from_env=from_env,
                                    to_env=to_env,
                                )
                                await send_camera_notifications(
                                    self.bot, embed, "camera_transfer_failed"
                                )
                    else:
                        await conn.execute(
                            """INSERT INTO camera_transfer_tasks
                               (id, sn, from_account_id, to_account_id, target_env,
                                task_status, created_at, updated_at, error_message)
                               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                               ON CONFLICT (id) DO NOTHING;""",
                            task_id,
                            sn,
                            from_acc_id,
                            to_acc_id,
                            target_env,
                            status,
                            created_at,
                            updated_at,
                            error_msg,
                        )

                        if status == "in_transfer":
                            embed = format_transfer_started_embed(
                                sn=sn,
                                from_email=from_email,
                                to_email=to_email,
                                target_env=target_env,
                                from_env=from_env,
                                to_env=to_env,
                            )
                            await send_camera_notifications(
                                self.bot, embed, "camera_transfer_started"
                            )

        except Exception as e:
            logger.error(f"Ошибка в check_camera_transfers: {e}", exc_info=True)
        finally:
            await conn.close()

    @check_camera_transfers_task.before_loop
    async def before_camera_transfers(self) -> None:
        await self.bot.wait_until_ready()

    # ── Расхождения камер ──────────────────────────────────

    @tasks.loop(seconds=DISCREPANCY_INTERVAL)
    async def check_camera_discrepancies_task(self) -> None:
        """Проверка новых расхождений в мониторинге камер."""
        conn = await connect_to_db()
        if not conn:
            logger.error("check_camera_discrepancies: не удалось подключиться к БД")
            return

        try:
            row = await conn.fetchrow(
                "SELECT last_id FROM last_discrepancy_check ORDER BY id DESC LIMIT 1;"
            )
            since_id = row["last_id"] if row else 0

            result = await get_camera_discrepancies(since_id=since_id, limit=50)
            if "error" in result or result.get("status") != "ok":
                logger.warning(f"Не удалось получить расхождения: {result.get('error')}")
                return

            discrepancies = result["data"]
            if not discrepancies:
                return

            discrepancies.sort(key=lambda x: x["id"])

            for d in discrepancies:
                discrepancy_id = d["id"]
                sn = d["sn"]
                uid = d.get("uid")
                type_ = d["type"]
                category = d["category"]
                summary = d["summary"]
                old_account_email = d.get("old_account_email")
                new_account_email = d.get("new_account_email")

                try:
                    detected_at = datetime.fromisoformat(
                        d["detected_at"].replace("Z", "+00:00")
                    )
                except ValueError:
                    detected_at = datetime.now(timezone.utc)

                await conn.execute(
                    """INSERT INTO camera_discrepancy_events
                       (id, sn, uid, type, category, detected_at, summary,
                        old_account_email, new_account_email, is_notified, created_at)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                       ON CONFLICT (id) DO UPDATE SET
                        summary = EXCLUDED.summary,
                        is_notified = EXCLUDED.is_notified""",
                    discrepancy_id,
                    sn,
                    uid,
                    type_,
                    category,
                    detected_at,
                    summary,
                    old_account_email,
                    new_account_email,
                    True,
                    datetime.now(timezone.utc),
                )

                embed = format_camera_discrepancy_embed(
                    summary=summary, detected_at=detected_at
                )
                await send_camera_notifications(self.bot, embed, "camera_status")

            final_id = discrepancies[-1]["id"]
            await conn.execute(
                """INSERT INTO last_discrepancy_check (last_id)
                   VALUES ($1) ON CONFLICT DO NOTHING""",
                final_id,
            )
            await conn.execute(
                "UPDATE last_discrepancy_check SET last_id = GREATEST(last_id, $1);",
                final_id,
            )

            logger.info(
                f"Обработано {len(discrepancies)} расхождений (до ID: {final_id})"
            )

        except Exception as e:
            logger.error(f"Ошибка в check_camera_discrepancies: {e}", exc_info=True)
        finally:
            await conn.close()

    @check_camera_discrepancies_task.before_loop
    async def before_camera_discrepancies(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    """Загрузка cog."""
    await bot.add_cog(CameraChecker(bot))
