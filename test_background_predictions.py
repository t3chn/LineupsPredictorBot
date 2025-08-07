#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from database.models import DatabaseManager
from utils.scheduler import DataScheduler
from config import LEAGUES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_background_prediction_system():
    """Test the background prediction generation system"""
    try:
        logger.info("🔍 Testing background prediction system...")
        
        db_manager = DatabaseManager()
        scheduler = DataScheduler(db_manager)
        
        logger.info("📊 Checking current database state...")
        
        with db_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as total_matches FROM matches WHERE match_date >= CURRENT_DATE")
                match_count = cursor.fetchone()['total_matches']
                
                cursor.execute("SELECT COUNT(*) as total_predictions FROM lineup_predictions")
                prediction_count = cursor.fetchone()['total_predictions']
                
                logger.info(f"📅 Upcoming matches: {match_count}")
                logger.info(f"🔮 Current predictions: {prediction_count}")
        
        logger.info("🚀 Running background prediction generation...")
        scheduler.update_all_lineup_predictions()
        
        with db_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as total_predictions FROM lineup_predictions")
                new_prediction_count = cursor.fetchone()['total_predictions']
                
                cursor.execute("""
                    SELECT l.name as league_name, COUNT(lp.id) as predictions
                    FROM leagues l
                    LEFT JOIN matches m ON l.id = m.league_id
                    LEFT JOIN lineup_predictions lp ON m.id = lp.match_id
                    WHERE m.match_date >= CURRENT_DATE
                    GROUP BY l.id, l.name
                    ORDER BY l.name
                """)
                league_predictions = cursor.fetchall()
                
                logger.info(f"🔮 New prediction count: {new_prediction_count}")
                logger.info(f"📈 Generated {new_prediction_count - prediction_count} new predictions")
                
                logger.info("📊 Predictions by league:")
                for league in league_predictions:
                    logger.info(f"   {league['league_name']}: {league['predictions']} predictions")
        
        if new_prediction_count > prediction_count:
            logger.info("✅ Background prediction system is working!")
            return True
        else:
            logger.warning("⚠️ No new predictions were generated")
            return False
            
    except Exception as e:
        logger.error(f"❌ Background prediction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_prediction_retrieval():
    """Test that predictions can be retrieved for matches"""
    try:
        logger.info("🔍 Testing prediction retrieval...")
        
        db_manager = DatabaseManager()
        
        with db_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT m.id as match_id, m.home_team_id, m.away_team_id,
                           ht.name as home_team, at.name as away_team
                    FROM matches m
                    JOIN teams ht ON m.home_team_id = ht.id
                    JOIN teams at ON m.away_team_id = at.id
                    WHERE m.match_date >= CURRENT_DATE
                    ORDER BY m.match_date
                    LIMIT 3
                """)
                matches = cursor.fetchall()
        
        for match in matches:
            logger.info(f"🏆 Testing match: {match['home_team']} vs {match['away_team']}")
            
            for team_id, team_name in [(match['home_team_id'], match['home_team']), 
                                     (match['away_team_id'], match['away_team'])]:
                prediction = db_manager.get_lineup_prediction(match['match_id'], team_id)
                
                if prediction:
                    logger.info(f"   ✅ {team_name}: Prediction available (confidence: {prediction.get('confidence_score', 'N/A')})")
                else:
                    logger.warning(f"   ❌ {team_name}: No prediction found")
        
        logger.info("✅ Prediction retrieval test completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Prediction retrieval test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("🧪 Starting background prediction system tests...")
    
    test1_success = test_background_prediction_system()
    test2_success = test_prediction_retrieval()
    
    if test1_success and test2_success:
        logger.info("🎉 All background prediction tests passed!")
        sys.exit(0)
    else:
        logger.error("❌ Some background prediction tests failed")
        sys.exit(1)
