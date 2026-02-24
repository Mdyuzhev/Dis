# gitlab_api.py
import logging
from typing import List
from urllib.parse import quote
import httpx
from datetime import datetime

from config_loader import GITLAB_API_URL, GITLAB_PRIVATE_TOKEN, CAMERA_MANAGE_API_URL, TESTIT_API_URL, TESTIT_API_KEY
from utils import extract_camera_sns

logger = logging.getLogger(__name__)

# Глобальный асинхронный клиент
GITLAB_CLIENT = httpx.AsyncClient(
    base_url=GITLAB_API_URL,
    headers={"PRIVATE-TOKEN": GITLAB_PRIVATE_TOKEN},
    timeout=60.0
)

TESTIT_CLIENT = httpx.AsyncClient(
    base_url=TESTIT_API_URL,
    headers={"Authorization": f"PrivateToken {TESTIT_API_KEY}"},
    timeout=10.0
)

CAMERA_CLIENT = httpx.AsyncClient(timeout=10.0)
ALLURE_CLIENT = httpx.AsyncClient(timeout=30.0)


async def get_pipelines(project_id):
    response = await GITLAB_CLIENT.get(f"/projects/{project_id}/pipelines")
    if response.status_code == 200:
        try:
            return response.json()
        except ValueError as e:
            logger.error(f"Ошибка парсинга JSON пайплайнов: {e}")
            return []
    else:
        logger.error(f"Ошибка получения пайплайнов: {response.status_code}")
        return []

async def get_recent_pipelines(project_id: str, updated_after: datetime = None) -> List[dict]:
    """
    Возвращает только недавние/обновлённые пайплайны.
    Используется в check_new_pipelines для оптимизации.
    """
    params = {}
    if updated_after:
        # Формат: ISO 8601 с Z → GitLab API понимает "2025-01-13T10:00:00Z"
        params["updated_after"] = updated_after.isoformat().replace("+00:00", "Z")
    params["per_page"] = 30
    params["sort"] = "desc"

    response = await GITLAB_CLIENT.get(f"/projects/{project_id}/pipelines", params=params)
    if response.status_code == 200:
        try:
            return response.json()
        except ValueError as e:
            logger.error(f"Ошибка парсинга JSON пайплайнов: {e}")
            return []
    else:
        logger.error(f"Ошибка получения пайплайнов: {response.status_code}")
        return []



async def get_pipeline_details(project_id, pipeline_id):
    response = await GITLAB_CLIENT.get(f"/projects/{project_id}/pipelines/{pipeline_id}")
    if response.status_code == 200:
        return response.json()
    else:
        logger.warning(f"Ошибка получения деталей пайплайна {pipeline_id}: {response.status_code}")
        return None


async def get_pipeline_schedules(project_id):
    response = await GITLAB_CLIENT.get(f"/projects/{project_id}/pipeline_schedules")
    if response.status_code == 200:
        try:
            return response.json()
        except ValueError as e:
            logger.error(f"Ошибка парсинга расписаний: {e}")
            return []
    else:
        logger.error(f"Ошибка получения расписаний: {response.status_code}")
        return []


async def get_merge_requests(project_id):
    response = await GITLAB_CLIENT.get(f"/projects/{project_id}/merge_requests?state=all")
    if response.status_code == 200:
        try:
            return response.json()
        except ValueError as e:
            logger.error(f"Ошибка парсинга MR: {e}")
            return []
    else:
        logger.error(f"Ошибка получения MR: {response.status_code}")
        return []


async def play_pipeline_schedule(project_id, schedule_id):
    response = await GITLAB_CLIENT.post(f"/projects/{project_id}/pipeline_schedules/{schedule_id}/play")
    return response.status_code in (200, 201)


async def get_pipeline_schedule_details(project_id, schedule_id):
    response = await GITLAB_CLIENT.get(f"/projects/{project_id}/pipeline_schedules/{schedule_id}")
    if response.status_code == 200:
        try:
            return response.json()
        except ValueError as e:
            logger.error(f"Ошибка парсинга деталей расписания: {e}")
            return None
    else:
        logger.warning(f"Ошибка получения деталей расписания {schedule_id}: {response.status_code}")
        return None


async def get_file_content(project_id, file_path):
    encoded_path = quote(file_path, safe='')
    url = f"/projects/{project_id}/repository/files/{encoded_path}/raw"
    response = await GITLAB_CLIENT.get(url)
    if response.status_code == 200:
        return response.text
    else:
        logger.error(f"Ошибка получения файла {file_path}: {response.status_code}")
        return None


async def update_file_content(project_id, file_path, new_content, branch="master"):
    encoded_path = quote(file_path, safe='')
    url = f"/projects/{project_id}/repository/files/{encoded_path}"
    payload = {
        "branch": branch,
        "content": new_content,
        "commit_message": f"chore(config): update {file_path} for test environment setup"
    }
    response = await GITLAB_CLIENT.put(url, json=payload)
    return response.status_code == 200


async def get_root_files(project_id, path):
    response = await GITLAB_CLIENT.get(
        f"/projects/{project_id}/repository/tree",  # ← Теперь project_id подставится реально
        params={"path": path, "recursive": "false"}
    )
    if response.status_code == 200:
        files = [item['name'] for item in response.json() if item['type'] == 'blob']
        return [f for f in files if f.endswith('.properties')]
    else:
        logger.error(f"Ошибка получения файлов из {path}: {response.status_code}")
        return []


async def get_allure_report_url(project_id, pipeline_id):
    response = await GITLAB_CLIENT.get(f"/projects/{project_id}/pipelines/{pipeline_id}/jobs")
    if response.status_code != 200:
        return None

    jobs = response.json()
    for job in jobs:
        if job["stage"] == "tests" and job["name"] == "test:test_schedules":
            log_response = await GITLAB_CLIENT.get(f"/projects/{project_id}/jobs/{job['id']}/trace", timeout=None)
            if log_response.status_code == 200:
                for line in log_response.text.splitlines():
                    if "Generate allure report. Url:" in line:
                        try:
                            return line.split("'")[1]
                        except IndexError:
                            continue
    return None


async def get_allure_summary(allure_report_url):
    """Асинхронно получает summary.json из Allure Report."""
    summary_url = f"{allure_report_url.rstrip('/')}/widgets/summary.json"
    try:
        response = await ALLURE_CLIENT.get(summary_url)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Ошибка получения Allure summary: {response.status_code} {response.text[:500]}")
            return None
    except Exception as e:
        logger.error(f"Ошибка запроса Allure отчёта: {e}")
        return None


async def get_camera_statuses_from_env(project_id: str, target_file: str) -> dict:
    from utils import parse_properties
    full_path = f"src/test/resources/{target_file}"
    file_content = await get_file_content(project_id, full_path)
    if not file_content:
        return {"error": f"Не удалось загрузить {full_path}"}

    props = parse_properties(file_content)
    camera_sns = extract_camera_sns(props)

    payload = {}
    sns = camera_sns["single"]
    if sns:
        payload["camera.sn"] = sns[0]
        for i, sn in enumerate(sns[1:], start=1):
            payload[f"camera{i}.sn"] = sn
    if camera_sns["list"]:
        payload["camera.sns"] = ",".join(camera_sns["list"])

    logger.debug(f"Запрос к camera-manage API: /api/cameras/status, payload={payload}")

    try:
        response = await CAMERA_CLIENT.post(f"{CAMERA_MANAGE_API_URL}/api/cameras/status", json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"Ошибка вызова camera-manage API: {error_msg}")
            return {"error": error_msg}
    except Exception as e:
        logger.exception("Исключение при вызове camera-manage API")
        return {"error": str(e)}


async def get_all_cameras_status() -> dict:
    try:
        response = await CAMERA_CLIENT.get(f"{CAMERA_MANAGE_API_URL}/api/cameras")
        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"Ошибка вызова camera-manage API: {error_msg}")
            return {"error": error_msg}
    except Exception as e:
        logger.exception("Исключение при вызове camera-manage API (все камеры)")
        return {"error": str(e)}


async def get_camera_transfer_tasks_batch(sns: list) -> dict:
    try:
        response = await CAMERA_CLIENT.post(
            f"{CAMERA_MANAGE_API_URL}/api/transfer-tasks/batch",
            json={"sns": sns}
        )
        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"Ошибка batch-запроса: {error_msg}")
            return {"error": error_msg}
    except Exception as e:
        logger.exception("Исключение при batch-запросе")
        return {"error": str(e)}


async def get_latest_transfer_task(sn: str) -> dict:
    try:
        response = await CAMERA_CLIENT.get(f"{CAMERA_MANAGE_API_URL}/api/transfer-task/latest/{sn}")
        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"Ошибка latest-запроса: {error_msg}")
            return {"error": error_msg}
    except Exception as e:
        logger.exception("Исключение при latest-запросе")
        return {"error": str(e)}


async def get_all_transfer_tasks_for_sn(sn: str) -> dict:
    try:
        response = await CAMERA_CLIENT.get(f"{CAMERA_MANAGE_API_URL}/api/transfer-tasks/{sn}")
        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"Ошибка истории трансферов для {sn}: {error_msg}")
            return {"error": error_msg}
    except Exception as e:
        logger.exception(f"Исключение при запросе истории трансферов для {sn}")
        return {"error": str(e)}

async def get_account_info(account_id: int) -> dict:
    """
    Получает информацию об одном аккаунте по ID.
    Пример: GET /api/accounts/2
    """
    try:
        url = f"{CAMERA_MANAGE_API_URL}/api/accounts/{account_id}"
        response = await CAMERA_CLIENT.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok" and "data" in data:
                return {"status": "ok", "data": data["data"]}
            else:
                logger.warning(f"API /api/accounts/{account_id} вернул некорректный формат: {data}")
                return {"error": "invalid_response_format"}
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"Ошибка получения аккаунта {account_id}: {error_msg}")
            return {"error": error_msg}
    except Exception as e:
        logger.exception(f"Исключение при запросе /api/accounts/{account_id}")
        return {"error": str(e)}

async def get_camera_discrepancies(since_id: int = 0, limit: int = 50) -> dict:
    """
    Запрашивает новые расхождения по камерам.
    :param since_id: Последний обработанный ID
    :param limit: лимит записей
    :return: JSON-ответ с данными
    """
    try:
        url = f"{CAMERA_MANAGE_API_URL}/api/notifications/discrepancies"
        params = {"since_id": since_id, "limit": limit}
        response = await CAMERA_CLIENT.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                return {"status": "ok", "data": data["data"]}
            else:
                logger.warning(f"API /discrepancies вернул некорректный статус: {data}")
                return {"error": "invalid_response_format"}
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"Ошибка при запросе /discrepancies: {error_msg}")
            return {"error": error_msg}

    except Exception as e:
        logger.exception("Исключение при вызове /api/notifications/discrepancies")
        return {"error": str(e)}

async def get_pipeline_variables(project_id, pipeline_id):
    response = await GITLAB_CLIENT.get(f"/projects/{project_id}/pipelines/{pipeline_id}/variables")
    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Ошибка получения переменных пайплайна {pipeline_id}: {response.status_code}")
        return []

async def get_testit_section_name(section_id: str) -> str:
    """
    Получает название секции по её UUID.
    """
    if not section_id or section_id == "—":
        return section_id

    try:
        response = await TESTIT_CLIENT.get(f"/api/v2/sections/{section_id}")
        if response.status_code == 200:
            data = response.json()
            return data.get("name", section_id)
        else:
            logger.warning(f"Test IT API returned {response.status_code}: {response.text}")
            return section_id
    except Exception as e:
        logger.error(f"Exception while fetching section {section_id}: {e}")
        return section_id

# === ОПЦИОНАЛЬНО: закрытие клиентов при завершении работы ===
async def shutdown_clients():
    await GITLAB_CLIENT.aclose()
    await CAMERA_CLIENT.aclose()
    await ALLURE_CLIENT.aclose()
    await TESTIT_CLIENT.aclose()