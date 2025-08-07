#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging
import time
from database.models import DatabaseManager
from handlers.bot_handlers import BotHandlers
from utils.scheduler import DataScheduler
from utils.logging_config import setup_logging
from config import TELEGRAM_BOT_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_bot_startup():
    """Test that the bot can start without crashing"""
    try:
        logger.info("🔍 Testing bot startup sequence...")
        
        logger.info("Testing database initialization...")
        db_manager = DatabaseManager()
        db_manager.init_database()
        logger.info("✅ Database initialized successfully")
        
        logger.info("Testing bot handlers creation...")
        bot_handlers = BotHandlers(db_manager)
        logger.info("✅ Bot handlers created successfully")
        
        logger.info("Testing scheduler startup...")
        scheduler = DataScheduler(db_manager)
        scheduler.start_scheduler_deferred()
        logger.info("✅ Scheduler started successfully")
        
        logger.info("Waiting 10 seconds to check for crashes...")
        await asyncio.sleep(10)
        
        scheduler.stop_scheduler()
        logger.info("✅ Scheduler stopped successfully")
        
        logger.info("🎉 Bot startup test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Bot startup test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_bot_startup())
    sys.exit(0 if success else 1)
