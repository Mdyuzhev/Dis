"""FastAPI вебхук для Test IT событий → Discord (shared bot instance)."""

import logging

import discord
from discord.ext import commands
from fastapi import FastAPI, Request, Response

from config_loader import WEBHOOK_SECRET
from db_operations import connect_to_db
from embeds import send_testit_notifications
from gitlab_api import get_testit_section_name
from helpers.testit_event_service import (
    register_new_participant_if_needed,
    save_testit_event,
    should_skip_notification_for_author,
)

logger = logging.getLogger(__name__)


def create_app(bot: commands.Bot) -> FastAPI:
    """Создаёт FastAPI-приложение с доступом к Discord-боту."""
    app = FastAPI()
    app.state.bot = bot

    @app.post("/testit-webhook")
    async def handle_testit_webhook(request: Request) -> dict | Response:
        if WEBHOOK_SECRET:
            secret = request.headers.get("x-testit-secret")
            if secret != WEBHOOK_SECRET:
                logger.warning("Invalid webhook secret")
                return Response(status_code=403)

        try:
            payload = await request.json()

            event_type = payload.get("eventType", "").strip()
            project_name = payload.get("project", "").strip()
            author = payload.get("author", "—")
            section_id = payload.get("section", "—")
            name = payload.get("name", "—")
            url = payload.get("url", "#")
            work_item_type = payload.get("workItemType", "элемент")

            # Определяем действие
            emoji_map = {
                "CREATED": ("🆕", "Создан", discord.Color.green()),
                "UPDATED": ("✏️", "Изменён", discord.Color.yellow()),
                "DELETED": ("🗑️", "Удалён", discord.Color.red()),
                "ARCHIVED": ("📦", "Архивирован", discord.Color.orange()),
                "RESTORED": ("🔄", "Восстановлен", discord.Color.blue()),
            }
            emoji, action, color = emoji_map.get(
                event_type, ("ℹ️", "Обновлён", discord.Color.greyple())
            )

            # Тип элемента
            type_map = {
                "TestCases": "тест-кейс",
                "CheckList": "чек-лист",
                "SharedStep": "общий шаг",
            }
            item_type_rus = type_map.get(work_item_type, "рабочий элемент")

            # Получаем имя секции
            if section_id and section_id not in ("—", "None", ""):
                section_name = await get_testit_section_name(section_id)
            else:
                section_name = section_id

            # Подключение к БД
            conn = await connect_to_db()
            if not conn:
                logger.error("Webhook: не удалось подключиться к БД")
                return Response(status_code=500)

            try:
                # Авто-регистрация участника
                await register_new_participant_if_needed(conn, author)

                # Пропускаем, если исключён
                if await should_skip_notification_for_author(conn, author):
                    return {"status": "ignored", "reason": "author_excluded"}

                # Сохраняем событие
                await save_testit_event(conn, payload, section_name)
            finally:
                await conn.close()

            # Формируем Embed
            embed = discord.Embed(
                title=f"{emoji} {action} {item_type_rus}",
                color=color,
                url=url if url != "#" else None,
            )
            embed.add_field(name="Автор", value=author, inline=True)
            embed.add_field(name="Проект", value=project_name, inline=True)
            embed.add_field(name="Секция", value=section_name or "—", inline=True)
            embed.add_field(name="Название", value=name, inline=False)
            embed.set_footer(text=f"Статус: {action}")

            # Рассылка
            sent_count, _ = await send_testit_notifications(app.state.bot, embed)

            if not sent_count:
                return {"status": "no_subscribers"}

            logger.info(f"Webhook Test IT: отправлено {sent_count} подписчикам")
            return {"status": "ok", "sent": sent_count}

        except Exception as e:
            logger.exception("Ошибка в testit_webhook")
            return Response(status_code=500)

    return app
