#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fetchers.transfermarkt_scraper import TransfermarktScraper
from database.models import DatabaseManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_match_scraper():
    """Debug transfermarkt match scraping issues"""
    try:
        logger.info("🔍 Testing transfermarkt scraper...")
        
        scraper = TransfermarktScraper()
        
        logger.info("Testing Premier League matches...")
        matches = scraper.scrape_league_matches('GB1', '2025')
        
        logger.info(f"📊 Found {len(matches)} matches")
        
        if matches:
            for i, match in enumerate(matches[:3]):
                logger.info(f"  {i+1}. {match['home_team_name']} vs {match['away_team_name']} - {match['match_date']}")
        else:
            logger.error("❌ No matches found - scraper is failing")
        
        return len(matches) > 0
        
    except Exception as e:
        logger.error(f"❌ Scraper test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_match_scraper()
