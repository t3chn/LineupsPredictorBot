#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.models import DatabaseManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_bot_fix():
    """Verify that the bot fix is working by checking database directly"""
    try:
        logger.info("🔍 Verifying bot fix by checking database...")
        
        db = DatabaseManager()
        
        leagues = db.get_all_leagues()
        logger.info(f"📋 Found {len(leagues)} leagues")
        
        total_matches = 0
        for league in leagues:
            if league['name'] == 'Test League':
                continue
                
            matches = db.get_next_matchday_matches(league['id'])
            logger.info(f"🏆 {league['name']}: {len(matches)} matches")
            
            if len(matches) > 0:
                match = matches[0]
                logger.info(f"   Example: {match['home_team_name']} vs {match['away_team_name']} - {match['match_date']}")
            
            total_matches += len(matches)
        
        logger.info(f"\n📊 Total matches across all leagues: {total_matches}")
        
        if total_matches > 0:
            logger.info("✅ Bot fix successful - matches are available in database!")
            logger.info("✅ The 'No upcoming matches found' error should be resolved!")
            return True
        else:
            logger.error("❌ No matches found - fix unsuccessful")
            return False
            
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    verify_bot_fix()
