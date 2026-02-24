"""Форматирование уведомлений в discord.Embed + рассылка."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import discord
from discord.ext import commands

from db_operations import connect_to_db

logger = logging.getLogger(__name__)

# Цвета по статусу пайплайна
STATUS_COLORS: Dict[str, discord.Color] = {
    "success": discord.Color.green(),
    "failed": discord.Color.red(),
    "running": discord.Color.blue(),
    "pending": discord.Color.yellow(),
}

STATUS_EMOJI: Dict[str, str] = {
    "success": "✅ Успешно",
    "failed": "❌ Ошибка",
    "running": "🔄 В процессе",
    "pending": "⏳ Ожидание",
}

MSK_TZ = timezone(timedelta(hours=3))

MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def _format_date_ru(dt: datetime) -> str:
    """Форматирует дату на русском: '24 февраля 2026 года'."""
    return f"{dt.day} {MONTHS_RU[dt.month - 1]} {dt.year} года"


def _format_duration(milliseconds: int) -> str:
    """Преобразует миллисекунды в читаемый формат."""
    total_seconds = milliseconds // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}ч {minutes}м {seconds}с"


# ── Пайплайны ──────────────────────────────────────────────


def format_pipeline_embed(
    project_id: str,
    project_name: str,
    stand_value: str,
    pipeline_id: int,
    ref: str,
    status: str,
    author_name: str,
    web_url: str,
    event_type: str = "update",
) -> discord.Embed:
    """Embed уведомления о пайплайне (старт/финиш/обновление)."""
    header = {
        "start": "▶️ Новый пайплайн запущен!",
        "finish": "⚠️ Пайплайн завершён!",
        "update": "📌 Обновление пайплайна",
    }.get(event_type, "📌 Пайплайн")

    color = STATUS_COLORS.get(status, discord.Color.greyple())
    status_text = STATUS_EMOJI.get(status, "❓ Неизвестно")

    embed = discord.Embed(title=header, color=color, url=web_url)
    embed.add_field(name="Проект", value=project_name, inline=True)
    embed.add_field(name="Окружение", value=stand_value, inline=True)
    embed.add_field(name="Статус", value=status_text, inline=True)
    embed.add_field(name="Ветка", value=ref, inline=True)
    embed.add_field(name="Автор", value=author_name, inline=True)
    embed.set_footer(text=f"Pipeline #{pipeline_id}")
    return embed


def add_allure_fields(
    embed: discord.Embed,
    allure_url: Optional[str],
    stats: Optional[Dict],
    time_stats: Optional[Dict],
) -> discord.Embed:
    """Добавляет поля Allure-отчёта и статистики тестов к embed."""
    if allure_url:
        embed.add_field(
            name="📋 Allure-отчёт",
            value=f"[Открыть]({allure_url})",
            inline=False,
        )
    else:
        embed.add_field(
            name="📋 Allure-отчёт",
            value="Не найден",
            inline=False,
        )

    if stats:
        passed = stats.get("passed", 0)
        failed = stats.get("failed", 0)
        broken = stats.get("broken", 0)
        skipped = stats.get("skipped", 0)
        total = stats.get("total", passed + failed + broken + skipped)
        executed = passed + failed + broken
        percent = round((passed / executed * 100), 2) if executed else 0.0

        if percent >= 95:
            emoji, comment = "🟢", "Высокая стабильность"
        elif percent >= 80:
            emoji, comment = "🟡", "Требует анализа"
        else:
            emoji, comment = "🔴", "Низкая стабильность"

        stats_text = (
            f"{emoji} Успешных: **{percent:.2f}%** — {comment}\n"
            f"🔢 Всего: {total}\n"
            f"✔️ Успешные: {passed} | ✖️ Проваленные: {failed}\n"
            f"⚠ Сломанные: {broken} | 🔍 Пропущенные: {skipped}"
        )
        embed.add_field(name="📊 Результаты прогона", value=stats_text, inline=False)

    if time_stats:
        start_ts = time_stats.get("start")
        stop_ts = time_stats.get("stop")
        duration_ms = time_stats.get("duration", 0)

        time_parts = []
        if start_ts:
            start_dt = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc).astimezone(MSK_TZ)
            time_parts.append(f"⏳ Начало: {start_dt.strftime('%H:%M')} — {_format_date_ru(start_dt)}")
        if stop_ts:
            stop_dt = datetime.fromtimestamp(stop_ts / 1000, tz=timezone.utc).astimezone(MSK_TZ)
            time_parts.append(f"⌛ Окончание: {stop_dt.strftime('%H:%M')} — {_format_date_ru(stop_dt)}")
        if duration_ms:
            total_sec = duration_ms // 1000
            hours, minutes = divmod(total_sec // 60, 60)
            time_parts.append(f"⏱ Общее время: {hours}ч {minutes}м")

        if time_parts:
            embed.add_field(
                name="⏱ Время выполнения",
                value="\n".join(time_parts),
                inline=False,
            )

    return embed


def add_test_statistics_from_db(
    embed: discord.Embed,
    tests_passed: Optional[int],
    tests_failed: Optional[int],
    duration_sec: Optional[int],
) -> discord.Embed:
    """Добавляет статистику из БД (когда Allure summary недоступен)."""
    if tests_passed is None and tests_failed is None:
        return embed

    passed = tests_passed or 0
    failed = tests_failed or 0
    total = passed + failed
    percent = round((passed / total * 100), 2) if total else 0.0

    if percent >= 95:
        emoji, comment = "🟢", "Высокая стабильность"
    elif percent >= 80:
        emoji, comment = "🟡", "Требует анализа"
    else:
        emoji, comment = "🔴", "Низкая стабильность"

    stats_text = (
        f"{emoji} Успешных: **{percent:.2f}%** — {comment}\n"
        f"✔️ Успешные: {passed} | ✖️ Проваленные: {failed}"
    )
    embed.add_field(name="📊 Результаты прогона", value=stats_text, inline=False)

    if duration_sec:
        hours, minutes = divmod(duration_sec // 60, 60)
        embed.add_field(name="⏱ Время", value=f"{hours}ч {minutes}м", inline=True)

    return embed


# ── Merge Requests ─────────────────────────────────────────


def format_mr_embed(
    project_name: str,
    mr_iid: int,
    title: str,
    author_name: str,
    source_branch: str,
    target_branch: str,
    web_url: str,
    status: str,
    is_new: bool = False,
) -> discord.Embed:
    """Embed уведомления о MR."""
    if is_new:
        header = "🚀 Новый MR создан!"
        color = discord.Color.blue()
    else:
        status_map = {
            "merged": ("✅ MR успешно слит!", discord.Color.green()),
            "closed": ("❌ MR закрыт.", discord.Color.red()),
            "opened": ("🔄 MR открыт заново.", discord.Color.blue()),
        }
        header, color = status_map.get(status, ("❓ Статус изменён", discord.Color.greyple()))

    embed = discord.Embed(title=header, color=color, url=web_url)
    embed.add_field(name="Проект", value=project_name, inline=True)
    embed.add_field(name="Автор", value=author_name, inline=True)
    embed.add_field(name="Заголовок", value=title, inline=False)
    embed.add_field(name="Ветка", value=f"`{source_branch}` → `{target_branch}`", inline=False)
    embed.set_footer(text=f"MR !{mr_iid}")
    return embed


# ── Камеры ─────────────────────────────────────────────────


def _status_icon(value: Optional[bool]) -> str:
    """Иконка статуса: True→🟢, False→🔴, None→⚪."""
    if value is True:
        return "🟢"
    if value is False:
        return "🔴"
    return "⚪"


def format_camera_status_embed(
    sn: str,
    email: str,
    env: str,
    changes: List[str],
    is_alive_vcfront: bool,
    is_active_agent: bool,
    is_online_agent: bool,
    is_active_vuf: bool,
) -> discord.Embed:
    """Embed об изменении статуса камеры."""
    embed = discord.Embed(
        title="⚠️ Статус камеры изменён",
        color=discord.Color.orange(),
    )
    embed.add_field(name="SN", value=sn, inline=True)
    embed.add_field(name="Аккаунт", value=email, inline=True)
    embed.add_field(name="Окружение", value=env, inline=True)
    embed.add_field(name="Изменения", value=", ".join(changes), inline=False)
    embed.add_field(
        name="Текущий статус",
        value=(
            f"{_status_icon(is_alive_vcfront)} VCF-Online\n"
            f"{_status_icon(is_active_agent)} AV-Active\n"
            f"{_status_icon(is_online_agent)} AV-Online\n"
            f"{_status_icon(is_active_vuf)} VUF"
        ),
        inline=False,
    )
    return embed


def format_new_camera_embed(
    sn: str,
    email: str,
    env: str,
    is_alive_vcfront: bool,
    is_active_agent: bool,
    is_online_agent: bool,
    is_active_vuf: bool,
) -> discord.Embed:
    """Embed о новой камере."""
    embed = discord.Embed(
        title="🆕 Новая камера",
        color=discord.Color.teal(),
    )
    embed.add_field(name="SN", value=sn, inline=True)
    embed.add_field(name="Аккаунт", value=email, inline=True)
    embed.add_field(name="Окружение", value=env, inline=True)
    embed.add_field(
        name="Статус",
        value=(
            f"{_status_icon(is_alive_vcfront)} VCF-Online\n"
            f"{_status_icon(is_active_agent)} AV-Active\n"
            f"{_status_icon(is_online_agent)} AV-Online\n"
            f"{_status_icon(is_active_vuf)} VUF"
        ),
        inline=False,
    )
    return embed


# ── Трансферы камер ────────────────────────────────────────


def format_transfer_started_embed(
    sn: str,
    from_email: str,
    to_email: str,
    target_env: str,
    from_env: Optional[str] = None,
    to_env: Optional[str] = None,
) -> discord.Embed:
    """Embed о начале перемещения камеры."""
    from_label = from_email + (f" ({from_env})" if from_env else "")
    to_label = to_email + (f" ({to_env})" if to_env else "")

    embed = discord.Embed(title="🔁 Начато перемещение камеры", color=discord.Color.blue())
    embed.add_field(name="SN", value=f"`{sn}`", inline=True)
    embed.add_field(name="Целевое окружение", value=f"`{target_env}`", inline=True)
    embed.add_field(name="Из", value=from_label, inline=False)
    embed.add_field(name="В", value=to_label, inline=False)
    return embed


def format_transfer_completed_embed(
    sn: str,
    from_email: str,
    to_email: str,
    target_env: str,
    from_env: Optional[str] = None,
    to_env: Optional[str] = None,
) -> discord.Embed:
    """Embed об успешном завершении перемещения."""
    from_label = from_email + (f" ({from_env})" if from_env else "")
    to_label = to_email + (f" ({to_env})" if to_env else "")

    embed = discord.Embed(title="✅ Перемещение завершено", color=discord.Color.green())
    embed.add_field(name="SN", value=f"`{sn}`", inline=True)
    embed.add_field(name="Окружение", value=f"`{target_env}`", inline=True)
    embed.add_field(name="Была в", value=from_label, inline=False)
    embed.add_field(name="Теперь в", value=to_label, inline=False)
    return embed


def format_transfer_failed_embed(
    sn: str,
    from_email: str,
    to_email: str,
    error: Optional[str] = None,
    from_env: Optional[str] = None,
    to_env: Optional[str] = None,
) -> discord.Embed:
    """Embed об ошибке при перемещении."""
    from_label = from_email + (f" ({from_env})" if from_env else "")
    to_label = to_email + (f" ({to_env})" if to_env else "")
    err = (error or "").strip() or "Неизвестная ошибка"

    embed = discord.Embed(title="❌ Ошибка перемещения камеры", color=discord.Color.red())
    embed.add_field(name="SN", value=f"`{sn}`", inline=True)
    embed.add_field(name="Из", value=from_label, inline=True)
    embed.add_field(name="В", value=to_label, inline=True)
    embed.add_field(name="Ошибка", value=f"```{err}```", inline=False)
    return embed


# ── Расхождения камер ──────────────────────────────────────


def format_camera_discrepancy_embed(
    summary: str,
    detected_at: datetime,
) -> discord.Embed:
    """Embed о расхождении в учёте камер."""
    local_dt = detected_at.astimezone(MSK_TZ)
    date_str = f"{local_dt.day} {MONTHS_RU[local_dt.month - 1]} {local_dt.year}"
    time_str = local_dt.strftime("%H:%M")

    embed = discord.Embed(
        title="⚠️ Обнаружено расхождение в учёте камер",
        description=summary,
        color=discord.Color.orange(),
    )
    embed.set_footer(text=f"📅 {time_str}, {date_str}")
    return embed


# ── Test IT статистика ─────────────────────────────────────


def format_daily_testit_stats_embed(
    stats: List[Dict],
    start_date: datetime,
    winner: Optional[str] = None,
    total_score: float = 0.0,
    no_activity: bool = False,
) -> discord.Embed:
    """Embed ежедневной статистики Test IT."""
    msk_dt = start_date.astimezone(MSK_TZ) if start_date.tzinfo else start_date.replace(tzinfo=timezone.utc).astimezone(MSK_TZ)
    date_str = f"{msk_dt.day} {MONTHS_RU[msk_dt.month - 1]}"

    embed = discord.Embed(
        title=f"🏆 Статистика Test IT — {date_str}",
        color=discord.Color.gold(),
    )

    total_created = 0
    total_updated = 0
    total_deleted = 0

    if no_activity or not stats:
        embed.description = "Нет активности за период"
    else:
        lines = []
        for item in stats:
            author = item["author"]
            created = int(item.get("created", 0)) or 0
            updated = int(item.get("updated", 0)) or 0
            deleted = int(item.get("deleted", 0)) or 0

            total_created += created
            total_updated += updated
            total_deleted += deleted

            actions = []
            if created > 0:
                actions.append(f"🆕 {created}")
            if updated > 0:
                actions.append(f"✏️ {updated}")
            if deleted > 0:
                actions.append(f"🗑️ {deleted}")

            if actions:
                lines.append(f"**{author}**: {' '.join(actions)}")

        embed.description = "\n".join(lines) if lines else "Нет активности за период"

    embed.add_field(
        name="📊 Всего за период",
        value=(
            f"🆕 Создано: **{total_created}**\n"
            f"✏️ Отредактировано: **{total_updated}**\n"
            f"🗑️ Удалено: **{total_deleted}**"
        ),
        inline=False,
    )

    if winner and total_score > 0:
        embed.add_field(
            name="🌟 Победитель дня",
            value=f"**{winner}** с результатом **{round(total_score, 2)}** баллов!",
            inline=False,
        )

    return embed


# ── Рассылка уведомлений ───────────────────────────────────


async def send_notifications(
    bot: commands.Bot,
    embed: discord.Embed,
    project_id: str,
    notification_type: str,
) -> int:
    """
    Рассылает embed подписчикам проекта.
    Возвращает количество успешных отправок.
    """
    conn = await connect_to_db()
    if not conn:
        logger.error("send_notifications: не удалось подключиться к БД")
        return 0

    sent = 0
    try:
        subs = await conn.fetch(
            """SELECT s.user_id, s.channel_id, s.thread_id, s.source_type
               FROM subscribers s
               WHERE s.project_id = $1 AND s.notification_type = $2;""",
            project_id, notification_type,
        )
        for sub in subs:
            try:
                await _deliver_embed(bot, sub, embed)
                sent += 1
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления ({notification_type}): {e}")
            await asyncio.sleep(0.5)
    finally:
        await conn.close()

    return sent


async def send_camera_notifications(
    bot: commands.Bot,
    embed: discord.Embed,
    notification_type: str,
) -> int:
    """
    Рассылает embed подписчикам камер (без привязки к project_id).
    Возвращает количество успешных отправок.
    """
    conn = await connect_to_db()
    if not conn:
        logger.error("send_camera_notifications: не удалось подключиться к БД")
        return 0

    sent = 0
    try:
        subs = await conn.fetch(
            """SELECT s.user_id, s.channel_id, s.thread_id, s.source_type
               FROM subscribers s
               WHERE s.notification_type = $1;""",
            notification_type,
        )
        for sub in subs:
            try:
                await _deliver_embed(bot, sub, embed)
                sent += 1
            except Exception as e:
                logger.error(f"Ошибка отправки камерного уведомления ({notification_type}): {e}")
            await asyncio.sleep(0.5)
    finally:
        await conn.close()

    return sent


async def send_testit_notifications(
    bot: commands.Bot,
    embed: discord.Embed,
) -> tuple[int, Optional[discord.Message]]:
    """
    Рассылает embed подписчикам testit_case.
    Возвращает (количество отправок, первое сообщение в thread для pin).
    """
    conn = await connect_to_db()
    if not conn:
        logger.error("send_testit_notifications: не удалось подключиться к БД")
        return 0, None

    sent = 0
    first_thread_msg: Optional[discord.Message] = None
    try:
        subs = await conn.fetch(
            """SELECT s.user_id, s.channel_id, s.thread_id, s.source_type
               FROM subscribers s
               WHERE s.notification_type = 'testit_case'
                 AND (s.project_id = '*' OR s.project_id IS NULL);""",
        )
        for sub in subs:
            try:
                msg = await _deliver_embed(bot, sub, embed)
                sent += 1
                if msg and sub["source_type"] == "thread" and first_thread_msg is None:
                    first_thread_msg = msg
            except Exception as e:
                logger.error(f"Ошибка отправки TestIT уведомления: {e}")
            await asyncio.sleep(0.5)
    finally:
        await conn.close()

    return sent, first_thread_msg


async def _deliver_embed(
    bot: commands.Bot,
    sub: dict,
    embed: discord.Embed,
) -> Optional[discord.Message]:
    """Отправляет embed в канал/тред/DM по данным подписки.

    Обрабатывает Forbidden (DM заблокированы) и NotFound (канал удалён).
    """
    source_type = sub["source_type"]

    try:
        if source_type == "dm":
            user = bot.get_user(sub["user_id"]) or await bot.fetch_user(sub["user_id"])
            return await user.send(embed=embed)

        if source_type == "thread" and sub["thread_id"]:
            thread = bot.get_channel(sub["thread_id"])
            if thread is None:
                thread = await bot.fetch_channel(sub["thread_id"])
            return await thread.send(embed=embed)

        # channel
        channel = bot.get_channel(sub["channel_id"])
        if channel is None:
            channel = await bot.fetch_channel(sub["channel_id"])
        return await channel.send(embed=embed)

    except discord.Forbidden:
        logger.warning(
            f"Нет прав на отправку: source={source_type}, "
            f"user={sub.get('user_id')}, channel={sub.get('channel_id')}"
        )
        return None
    except discord.NotFound:
        logger.warning(
            f"Канал/пользователь не найден: source={source_type}, "
            f"user={sub.get('user_id')}, channel={sub.get('channel_id')}"
        )
        return None
