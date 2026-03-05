"""Main entry point for the referral bot.

Runs both the aiogram bot polling and the aiohttp web server concurrently.
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from config import BOT_TOKEN, WEBHOOK_PORT
import web_server
from handlers import leaderboard, curator, admin

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main function to run bot and web server concurrently."""

    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register handlers
    dp.include_router(leaderboard.router)
    dp.include_router(curator.router)
    dp.include_router(admin.router)

    # Set bot reference in web_server for webhook handling
    web_server.set_bot(bot)

    # Create aiohttp app
    app = web.Application()
    app.router.add_post('/webhook', web_server.webhook_handler)
    app.router.add_get('/health', web_server.health_handler)

    # Create web runner
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEBHOOK_PORT)

    try:
        # Start web server
        await site.start()
        logger.info(f"Web server started on port {WEBHOOK_PORT}")

        # Start bot polling
        logger.info("Bot polling started")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
