#!/usr/bin/env python3

import os
import subprocess
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_bot_running():
    """Ensure bot is running, restart if needed"""
    try:
        result = subprocess.run(['pgrep', '-f', 'python.*main.py'], 
                              capture_output=True, text=True)
        
        if len(result.stdout.strip()) == 0:
            logger.info(f"🔄 Bot not running, starting it...")
            
            subprocess.run(['pkill', '-f', 'python.*main.py'], capture_output=True)
            
            subprocess.Popen(['python', '/home/ubuntu/fantasy_football_bot/main.py'], 
                           cwd='/home/ubuntu/fantasy_football_bot',
                           stdout=open('/home/ubuntu/fantasy_football_bot/fantasy_football_bot.log', 'a'),
                           stderr=subprocess.STDOUT)
            
            logger.info("✅ Bot started")
        else:
            logger.info("✅ Bot is already running")
            
    except Exception as e:
        logger.error(f"❌ Error ensuring bot is running: {e}")

if __name__ == "__main__":
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{current_time}] Checking bot status...")
    ensure_bot_running()
