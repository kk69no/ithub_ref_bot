"""
Точка входа: aiogram polling + aiohttp веб-сервер (OAuth callback).
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, WEBHOOK_PORT
import database as db
import web_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    # Инициализируем БД
    await db.init_db()

    # Бот + диспетчер
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем роутеры (порядок важен!)
    from handlers import student, applicant, leaderboard, curator, admin
    dp.include_router(student.router)
    dp.include_router(applicant.router)
    dp.include_router(leaderboard.router)
    dp.include_router(curator.router)
    dp.include_router(admin.router)

    # Передаём бот в web_server для отправки уведомлений
    web_server.set_bot(bot)

    # Запускаем aiohttp для OAuth-callback
    from aiohttp import web
    app = web_server.create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)

    try:
        await site.start()
        logger.info("Web server started on port %s", WEBHOOK_PORT)
        logger.info("Bot polling started")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
