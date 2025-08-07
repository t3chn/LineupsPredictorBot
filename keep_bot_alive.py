#!/usr/bin/env python3

import os
import sys
import time
import subprocess
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_SCRIPT_PATH = "/home/ubuntu/fantasy_football_bot/main.py"
BOT_LOG_PATH = "/home/ubuntu/fantasy_football_bot/fantasy_football_bot.log"
TELEGRAM_BOT_TOKEN = os.getenv('Telegram_Token')
CHECK_INTERVAL = 60

def is_bot_running():
    """Check if the bot process is running"""
    try:
        result = subprocess.run(['pgrep', '-f', 'python.*main.py'], 
                              capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except Exception as e:
        logger.error(f"Error checking bot process: {e}")
        return False

def test_bot_responsiveness():
    """Test if bot responds to Telegram API calls"""
    if not TELEGRAM_BOT_TOKEN:
        return False
        
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
        response = requests.get(url, timeout=10)
        return response.status_code == 200 and response.json().get('ok', False)
    except Exception as e:
        logger.error(f"Bot responsiveness test failed: {e}")
        return False

def restart_bot():
    """Restart the bot process"""
    try:
        logger.info("🔄 Restarting bot...")
        
        subprocess.run(['pkill', '-f', 'python.*main.py'], capture_output=True)
        time.sleep(5)
        
        subprocess.Popen(['python', BOT_SCRIPT_PATH], 
                       cwd='/home/ubuntu/fantasy_football_bot',
                       stdout=open(BOT_LOG_PATH, 'a'),
                       stderr=subprocess.STDOUT)
        
        time.sleep(10)
        
        if is_bot_running():
            logger.info("✅ Bot restarted successfully")
            return True
        else:
            logger.error("❌ Bot restart failed")
            return False
            
    except Exception as e:
        logger.error(f"Error restarting bot: {e}")
        return False

def main():
    """Main keep-alive loop"""
    logger.info("🚀 Starting bot keep-alive monitor...")
    
    while True:
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if not is_bot_running():
                logger.warning(f"[{current_time}] ⚠️ Bot process not running")
                restart_bot()
            elif not test_bot_responsiveness():
                logger.warning(f"[{current_time}] ⚠️ Bot not responsive to Telegram API")
                restart_bot()
            else:
                logger.info(f"[{current_time}] ✅ Bot is running and responsive")
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("🛑 Keep-alive monitor stopped")
            break
        except Exception as e:
            logger.error(f"Error in keep-alive loop: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
