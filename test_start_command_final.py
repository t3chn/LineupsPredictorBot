#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging
from unittest.mock import Mock, AsyncMock
from handlers.bot_handlers import BotHandlers
from database.models import DatabaseManager
from config import LEAGUES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_start_command():
    """Test that /start command works properly"""
    try:
        logger.info("🔍 Testing /start command functionality...")
        
        db_manager = DatabaseManager()
        bot_handlers = BotHandlers(db_manager)
        
        mock_update = Mock()
        mock_update.effective_user.id = 12345
        mock_update.message.reply_text = AsyncMock()
        mock_context = Mock()
        
        await bot_handlers.start_command(mock_update, mock_context)
        
        if mock_update.message.reply_text.called:
            call_args = mock_update.message.reply_text.call_args
            message_text = call_args[0][0]
            reply_markup = call_args[1]['reply_markup']
            
            logger.info("✅ /start command executed successfully")
            logger.info(f"Message: {message_text[:100]}...")
            logger.info(f"Keyboard buttons: {len(reply_markup.inline_keyboard)}")
            
            if "Welcome to Fantasy Football Lineup Predictor" in message_text:
                logger.info("✅ Welcome message is correct")
            else:
                logger.error("❌ Welcome message is incorrect")
                return False
            
            if len(reply_markup.inline_keyboard) == len(LEAGUES):
                logger.info("✅ All league buttons are present")
            else:
                logger.error(f"❌ Expected {len(LEAGUES)} league buttons, got {len(reply_markup.inline_keyboard)}")
                return False
            
            logger.info("🎉 /start command test completed successfully!")
            return True
        else:
            logger.error("❌ /start command did not send a reply")
            return False
            
    except Exception as e:
        logger.error(f"❌ /start command test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_start_command())
    sys.exit(0 if success else 1)
