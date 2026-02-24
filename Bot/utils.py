"""Утилиты бота: определение стенда, обогащение Allure-данными."""

import logging
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)


async def find_stand_and_schedule_id(
    project_id: str, pipeline_id: int
) -> tuple[Optional[str], Optional[int]]:
    """
    Определяет стенд (STAND) и ID расписания для пайплайна.
    Запрашивает детали каждого расписания напрямую.
    """
    from gitlab_api import get_pipeline_schedules, get_pipeline_schedule_details

    schedules_list = await get_pipeline_schedules(project_id)
    if not schedules_list:
        return None, None

    schedule_ids = [s["id"] for s in schedules_list]

    for sid in schedule_ids:
        try:
            details = await get_pipeline_schedule_details(project_id, sid)
            if not details:
                continue

            last_pipeline = details.get("last_pipeline")
            if not last_pipeline or last_pipeline["id"] != pipeline_id:
                continue

            for var in details.get("variables", []):
                if var["key"] == "STAND":
                    value = var["value"].strip().lower()
                    return value, sid

            description = (details.get("description") or "").strip().lower()
            if "p1" in description:
                return "p1", sid
            elif any(k in description for k in ("staging", "stage")):
                return "staging", sid
            elif "demo" in description:
                return "demo", sid
            elif "prod" in description:
                return "prod", sid

            break

        except Exception as e:
            logger.warning(f"Ошибка при обработке расписания {sid}: {e}")
            continue

    return None, None


async def enrich_pipeline_with_allure_data(
    get_allure_report_url_func: Callable[..., Coroutine],
    get_allure_summary_func: Callable[..., Coroutine],
    db_conn: Any,
    project_id: str,
    pipeline_id: int,
    existing_row: dict,
) -> Dict[str, Any]:
    """
    Анализирует Allure-данные для пайплайна и обновляет БД.
    Возвращает словарь с: allure_url, stats, time_stats, message_addon, has_new_data.
    """
    data: Dict[str, Any] = {
        "allure_url": None,
        "stats": None,
        "time_stats": None,
        "message_addon": "",
        "has_new_data": False,
    }

    if existing_row["allure_report_url"]:
        data["allure_url"] = existing_row["allure_report_url"]
        data["message_addon"] += f"\n📋 [Ссылка на Allure-отчёт]({existing_row['allure_report_url']})"
    else:
        url = await get_allure_report_url_func(project_id, pipeline_id)
        if url:
            data["allure_url"] = url
            data["message_addon"] += f"\n📋 [Ссылка на Allure-отчёт]({url})"

            summary = await get_allure_summary_func(url)
            if summary:
                stats = summary.get("statistic", {})
                time_stats = summary.get("time", {})

                passed = stats.get("passed", 0)
                failed = stats.get("failed", 0)
                duration = time_stats.get("duration", 0) // 1000

                await db_conn.execute(
                    """UPDATE pipeline_states
                       SET allure_report_url=$1, tests_passed=$2, tests_failed=$3, duration_sec=$4
                       WHERE pipeline_id=$5""",
                    url, passed, failed, duration, pipeline_id,
                )

                data["stats"] = stats
                data["time_stats"] = time_stats
                data["has_new_data"] = True
            else:
                data["message_addon"] += "\n📊 Статистика тестов недоступна."
        else:
            data["message_addon"] += "\n📋 Allure-отчёт не найден."

    if not data["stats"] and data["allure_url"]:
        summary = await get_allure_summary_func(data["allure_url"])
        if summary:
            stats = summary.get("statistic", {})
            time_stats = summary.get("time", {})

            passed = stats.get("passed", 0)
            failed = stats.get("failed", 0)
            duration = time_stats.get("duration", 0) // 1000

            if passed > 0 or failed > 0:
                await db_conn.execute(
                    """UPDATE pipeline_states
                       SET tests_passed=$1, tests_failed=$2, duration_sec=$3
                       WHERE pipeline_id=$4""",
                    passed, failed, duration, pipeline_id,
                )

                data["stats"] = stats
                data["time_stats"] = time_stats
                data["has_new_data"] = True

    return data
