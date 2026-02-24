import json
import os


def load_config() -> dict:
    """Загрузка конфигурации из config.json."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        raise FileNotFoundError(f"Конфигурационный файл не найден: {config_path}")


config = load_config()


def _get_value(key: str, env_var: str | None = None, default=None):
    """
    Получает значение: сначала из env, потом из config.json, иначе default.
    Если env_var не указан — использует key как имя переменной окружения.
    """
    env_key = env_var or key.upper()
    value = os.getenv(env_key)
    if value is not None:
        return value
    return config.get(key, default)


# --- Discord ---
DISCORD_BOT_TOKEN: str = _get_value("discord_bot_token")
DISCORD_GUILD_ID: int = int(_get_value("discord_guild_id", default=0))
DISCORD_ADMIN_ROLE: str = _get_value("discord_admin_role", default="BotAdmin")

# --- GitLab ---
GITLAB_API_URL: str = _get_value("gitlab_api_url")
GITLAB_PRIVATE_TOKEN: str = _get_value("gitlab_private_token")
FIXED_PROJECTS: dict = config.get("fixed_projects", {})

# --- Database ---
DB_CONFIG: dict = config.get("database", {})

# --- Allure ---
ALLURE_REPORT_URL: str = _get_value("allure_report_url", default="")

# --- Jobs ---
JOBS_CONFIG: dict = config.get("jobs", {})

# --- Camera ---
CAMERA_MANAGE_API_URL: str = _get_value("camera_manage_api_url")

# --- TestIT Webhook ---
WEBHOOK_SECRET: str = os.getenv("TESTIT_WEBHOOK_SECRET", config.get("webhook_secret"))
WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", config.get("webhook_port", 8000)))
TESTIT_API_URL: str = os.getenv("TESTIT_API_URL", config.get("testit_api_url"))
TESTIT_API_KEY: str = os.getenv("TESTIT_API_KEY", config.get("testit_api_key"))
