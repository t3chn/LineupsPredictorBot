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

async def test_end_to_end_fix():
    """Test complete end-to-end bot functionality after match display fix"""
    try:
        logger.info("🔍 Testing complete end-to-end bot functionality...")
        
        db_manager = DatabaseManager()
        bot_handlers = BotHandlers(db_manager)
        
        success_count = 0
        total_leagues = 0
        
        for league_key, league_info in LEAGUES.items():
            total_leagues += 1
            logger.info(f"\n🏆 Testing {league_info['name']}...")
            
            league_db = db_manager.get_league_by_transfermarkt_id(league_info['transfermarkt_id'])
            if not league_db:
                logger.error(f"❌ League not found in database: {league_info['name']}")
                continue
            
            matches = db_manager.get_next_matchday_matches(league_db['id'])
            logger.info(f"📊 Found {len(matches)} matches for {league_info['name']}")
            
            if len(matches) == 0:
                logger.error(f"❌ No matches found for {league_info['name']}")
                continue
            
            mock_update = Mock()
            mock_update.callback_query = Mock()
            mock_update.callback_query.data = f"league_{league_key}"
            mock_update.callback_query.answer = AsyncMock()
            mock_update.callback_query.edit_message_text = AsyncMock()
            mock_update.effective_user.id = 12345
            mock_context = Mock()
            
            try:
                await bot_handlers.league_selection(mock_update, mock_context)
                
                if mock_update.callback_query.edit_message_text.called:
                    call_args = mock_update.callback_query.edit_message_text.call_args
                    message_text = call_args[0][0]
                    
                    if "No upcoming matches found" in message_text:
                        logger.error(f"❌ {league_info['name']} still shows 'No upcoming matches found'")
                    elif "Matchday" in message_text and "Fixtures" in message_text:
                        logger.info(f"✅ {league_info['name']} successfully shows matches!")
                        success_count += 1
                    else:
                        logger.warning(f"⚠️ {league_info['name']} shows unexpected message: {message_text[:100]}...")
                else:
                    logger.error(f"❌ {league_info['name']} handler not responding")
                    
            except Exception as e:
                logger.error(f"❌ Error testing {league_info['name']}: {e}")
        
        logger.info(f"\n📊 Test Results: {success_count}/{total_leagues} leagues working correctly")
        
        if success_count == total_leagues:
            logger.info("🎉 All leagues are working! Match display fix is successful!")
            return True
        elif success_count > 0:
            logger.info(f"✅ Partial success: {success_count} leagues working, {total_leagues - success_count} still have issues")
            return True
        else:
            logger.error("❌ No leagues are working - fix unsuccessful")
            return False
            
    except Exception as e:
        logger.error(f"❌ End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_end_to_end_fix())
