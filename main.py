import asyncio
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from database.models import DatabaseManager
from handlers.bot_handlers import BotHandlers
from utils.scheduler import DataScheduler
from utils.logging_config import setup_logging
from config import TELEGRAM_BOT_TOKEN

logger = setup_logging()

async def main():
    """Main function to run the bot"""
    try:
        logger.info("Starting Fantasy Football Lineup Predictor Bot")
        
        if not TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
            return
        
        logger.info("Initializing database...")
        db_manager = DatabaseManager()
        db_manager.init_database()
        logger.info("Database initialized successfully")
        
        bot_handlers = BotHandlers(db_manager)
        
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", bot_handlers.start_command))
        application.add_handler(CommandHandler("help", bot_handlers.help_command))
        
        application.add_handler(CallbackQueryHandler(
            bot_handlers.league_selection, 
            pattern="^league_"
        ))
        application.add_handler(CallbackQueryHandler(
            bot_handlers.match_selection, 
            pattern="^match_"
        ))
        application.add_handler(CallbackQueryHandler(
            bot_handlers.team_selection, 
            pattern="^team_"
        ))
        application.add_handler(CallbackQueryHandler(
            bot_handlers.refresh_prediction, 
            pattern="^refresh_"
        ))
        application.add_handler(CallbackQueryHandler(
            bot_handlers.back_to_leagues, 
            pattern="^back_to_leagues$"
        ))
        
        application.add_error_handler(bot_handlers.error_handler)
        
        logger.info("Starting data scheduler...")
        scheduler = DataScheduler(db_manager)
        scheduler.start_scheduler_deferred()
        
        logger.info("Starting bot...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        logger.info("Bot is running! Press Ctrl+C to stop.")
        
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Received stop signal")
        finally:
            logger.info("Stopping bot...")
            scheduler.stop_scheduler()
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            logger.info("Bot stopped")
            
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
