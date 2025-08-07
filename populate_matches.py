#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.models import DatabaseManager
from fetchers.transfermarkt_scraper import TransfermarktScraper
from config import LEAGUES
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def populate_matches():
    """Populate matches for all leagues"""
    try:
        db = DatabaseManager()
        scraper = TransfermarktScraper()
        
        logger.info("🏆 Starting match population for all leagues...")
        
        for league_key, league_info in LEAGUES.items():
            logger.info(f"\n📋 Processing {league_info['name']}...")
            
            league_db = db.get_league_by_transfermarkt_id(league_info['transfermarkt_id'])
            if not league_db:
                logger.error(f"League not found: {league_info['name']}")
                continue
            
            league_id = league_db['id']
            
            logger.info(f"Preserving existing matches for {league_info['name']}")
            
            matches = scraper.scrape_league_matches(league_info['transfermarkt_id'], league_info['season'])
            
            logger.info(f"📊 Found {len(matches)} matches for {league_info['name']}")
            
            matches_inserted = 0
            for match_data in matches:
                try:
                    home_team_id = db.get_or_create_team(
                        match_data['home_team_name'],
                        league_id,
                        match_data['home_team_transfermarkt_id']
                    )
                    
                    away_team_id = db.get_or_create_team(
                        match_data['away_team_name'],
                        league_id,
                        match_data['away_team_transfermarkt_id']
                    )
                    
                    if home_team_id and away_team_id:
                        match_id = db.insert_match(
                            home_team_id=home_team_id,
                            away_team_id=away_team_id,
                            league_id=league_id,
                            match_date=match_data['match_date'],
                            matchday=match_data['matchday'],
                            transfermarkt_id=match_data['transfermarkt_match_id']
                        )
                        if match_id:
                            matches_inserted += 1
                except Exception as e:
                    logger.error(f"Error inserting match: {e}")
                    continue
            
            logger.info(f"✅ Inserted {matches_inserted} matches for {league_info['name']}")
            time.sleep(2)
        
        logger.info("\n🎉 Match population completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error populating matches: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    populate_matches()
