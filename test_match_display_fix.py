#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging
from unittest.mock import Mock, AsyncMock
from handlers.bot_handlers import BotHandlers
from database.models import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_match_display_fix():
    """Test that match display is now working"""
    try:
        logger.info("🔍 Testing match display fix...")
        
        db_manager = DatabaseManager()
        bot_handlers = BotHandlers(db_manager)
        
        leagues = db_manager.get_all_leagues()
        premier_league = next((l for l in leagues if 'Premier' in l['name']), None)
        
        if not premier_league:
            logger.error("❌ Premier League not found")
            return False
        
        matches = db_manager.get_next_matchday_matches(premier_league['id'])
        logger.info(f"📊 Found {len(matches)} matches for Premier League")
        
        if len(matches) == 0:
            logger.error("❌ Still no matches found - fix unsuccessful")
            return False
        
        mock_update = Mock()
        mock_update.callback_query = Mock()
        mock_update.callback_query.data = "league_GB1"
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()
        mock_update.effective_user.id = 12345
        mock_context = Mock()
        
        await bot_handlers.league_selection(mock_update, mock_context)
        
        if mock_update.callback_query.edit_message_text.called:
            call_args = mock_update.callback_query.edit_message_text.call_args
            message_text = call_args[0][0]
            
            if "No upcoming matches found" in message_text:
                logger.error("❌ Bot still shows 'No upcoming matches found'")
                return False
            elif "Upcoming Matches" in message_text or "Fixtures" in message_text:
                logger.info("✅ Bot successfully shows matches!")
                return True
        
        logger.error("❌ Bot handler not responding correctly")
        return False
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_match_display_fix())
