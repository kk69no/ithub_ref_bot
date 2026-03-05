"""
Точка входа — запуск Telegram-бота реферальной программы IThub Нальчик.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import student, applicant, curator, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    # Инициализация БД
    await init_db()
    logger.info("База данных инициализирована.")

    # Бот и диспетчер
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем роутеры (порядок важен!)
    dp.include_router(admin.router)      # /admin — приоритетнее
    dp.include_router(student.router)    # /start + меню студента
    dp.include_router(applicant.router)  # FSM заявки абитуриента
    dp.include_router(curator.router)    # callback-и куратора

    logger.info("Бот запускается...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
