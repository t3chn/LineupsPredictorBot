#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging
import time
from unittest.mock import Mock, AsyncMock
from handlers.bot_handlers import BotHandlers
from database.models import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_start_command_health():
    """Test /start command health and responsiveness"""
    try:
        logger.info("🔍 Testing /start command health...")
        
        db_manager = DatabaseManager()
        bot_handlers = BotHandlers(db_manager)
        
        mock_update = Mock()
        mock_update.effective_user.id = 12345
        mock_update.message.reply_text = AsyncMock()
        mock_context = Mock()
        
        start_time = time.time()
        
        await bot_handlers.start_command(mock_update, mock_context)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        if mock_update.message.reply_text.called:
            call_args = mock_update.message.reply_text.call_args
            message_text = call_args[0][0]
            
            if "Welcome to Fantasy Football Lineup Predictor" in message_text:
                logger.info(f"✅ /start command healthy - responded in {response_time:.2f}s")
                return True, response_time
            else:
                logger.error("❌ /start command returned incorrect message")
                return False, response_time
        else:
            logger.error("❌ /start command did not respond")
            return False, response_time
            
    except Exception as e:
        logger.error(f"❌ /start command test failed: {e}")
        return False, 0

async def check_bot_process():
    """Check if bot process is running"""
    try:
        import subprocess
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        
        if 'python main.py' in result.stdout:
            logger.info("✅ Bot process is running")
            return True
        else:
            logger.error("❌ Bot process not found")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to check bot process: {e}")
        return False

async def check_database_health():
    """Check database connectivity and basic data"""
    try:
        db_manager = DatabaseManager()
        
        with db_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM leagues")
                result = cursor.fetchone()
                league_count = result['count'] if result and 'count' in result else (result[0] if result else 0)
                
                cursor.execute("SELECT COUNT(*) FROM teams")
                result = cursor.fetchone()
                team_count = result['count'] if result and 'count' in result else (result[0] if result else 0)
                
                cursor.execute("SELECT COUNT(*) FROM matches WHERE match_date >= CURRENT_DATE")
                result = cursor.fetchone()
                upcoming_matches = result['count'] if result and 'count' in result else (result[0] if result else 0)
                
        if league_count > 0 and team_count > 0:
            logger.info(f"✅ Database healthy - {league_count} leagues, {team_count} teams, {upcoming_matches} upcoming matches")
            return True
        else:
            logger.error(f"❌ Database appears empty - {league_count} leagues, {team_count} teams")
            return False
        
    except Exception as e:
        logger.error(f"❌ Database health check failed: {e}")
        return False

async def run_health_check():
    """Run complete health check"""
    logger.info("🏥 Starting bot health check...")
    
    results = {
        'process': await check_bot_process(),
        'database': await check_database_health(),
        'start_command': False,
        'response_time': 0
    }
    
    start_healthy, response_time = await test_start_command_health()
    results['start_command'] = start_healthy
    results['response_time'] = response_time
    
    all_healthy = all([results['process'], results['database'], results['start_command']])
    
    if all_healthy:
        logger.info(f"🎉 Bot is fully healthy! Response time: {response_time:.2f}s")
    else:
        failed_checks = [k for k, v in results.items() if not v and k != 'response_time']
        logger.error(f"⚠️ Bot health issues detected: {failed_checks}")
    
    return results

if __name__ == "__main__":
    results = asyncio.run(run_health_check())
    
    if results['start_command'] and results['database'] and results['process']:
        sys.exit(0)
    else:
        sys.exit(1)
