import schedule
import time
import threading
import logging
from datetime import datetime
from fetchers.transfermarkt_scraper import TransfermarktScraper
from fetchers.news_scraper import NewsScraper
from database.models import DatabaseManager
from analyzers.lineup_predictor import LineupPredictor
from config import LEAGUES, UPDATE_INTERVAL_HOURS

logger = logging.getLogger(__name__)

class DataScheduler:
    def __init__(self, db_manager):
        self.db = db_manager
        self.transfermarkt_scraper = TransfermarktScraper()
        self.news_scraper = NewsScraper()
        self.predictor = LineupPredictor(db_manager)
        self.running = False
        self.scheduler_thread = None
    
    def start_scheduler(self):
        """Start the data update scheduler with immediate updates (legacy method)"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        
        schedule.every(1).hours.do(self.update_matches_only)
        schedule.every(UPDATE_INTERVAL_HOURS).hours.do(self.update_all_data)
        
        self.update_matches_only()
        self.update_all_data()
        
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info(f"Data scheduler started - updates every {UPDATE_INTERVAL_HOURS} hours")
    
    def start_scheduler_deferred(self):
        """Start the data update scheduler without blocking initial updates"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        
        schedule.every(1).hours.do(self.update_matches_only)
        schedule.every(5).hours.do(self.update_all_lineup_predictions)
        schedule.every(UPDATE_INTERVAL_HOURS).hours.do(self.update_all_data)
        
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        def delayed_initial_update():
            time.sleep(30)
            try:
                logger.info("🔄 Running delayed initial data update...")
                self.update_matches_only()
                self.generate_initial_predictions()
                logger.info("✅ Delayed initial data update completed")
            except Exception as e:
                logger.error(f"❌ Delayed initial data update failed: {e}")
        
        initial_update_thread = threading.Thread(target=delayed_initial_update, daemon=True)
        initial_update_thread.start()
        
        logger.info(f"Data scheduler started in deferred mode - initial update in 30s, then every {UPDATE_INTERVAL_HOURS} hours")
    
    def stop_scheduler(self):
        """Stop the data update scheduler"""
        self.running = False
        schedule.clear()
        logger.info("Data scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(300)  # Wait 5 minutes on error
    
    def update_all_data(self):
        """Update all data sources with smart squad policy"""
        logger.info("🔄 Starting comprehensive data update...")
        
        try:
            for league_key, league_info in LEAGUES.items():
                self.update_league_data(league_key, league_info)
            
            current_date = datetime.now()
            season_start = datetime(2025, 8, 1)  # Approximate season start
            
            if current_date < season_start:
                logger.info("📅 Pre-season mode: Updating full squad rosters")
                self.update_squad_data()
            else:
                logger.info("⚽ Season active: Only updating injuries and suspensions")
                self.update_injuries_and_suspensions()
            
            logger.info("✅ Comprehensive data update completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Error in comprehensive data update: {e}")
    
    def update_injuries_and_suspensions(self):
        """Update only player injuries and suspensions (season-active mode)"""
        try:
            logger.info("🏥 Updating injuries and suspensions...")
            
            for league_key, league_info in LEAGUES.items():
                try:
                    league_db = self.db.get_league_by_transfermarkt_id(league_info['transfermarkt_id'])
                    if not league_db:
                        continue
                    
                    with self.db.get_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("""
                                SELECT id, transfermarkt_id, name 
                                FROM teams 
                                WHERE league_id = %s
                            """, (league_db['id'],))
                            teams = cursor.fetchall()
                    
                    for team in teams:
                        if team.get('transfermarkt_id'):
                            try:
                                injuries = self.transfermarkt_scraper.scrape_player_injuries(team['transfermarkt_id'])
                                
                                for injury_data in injuries:
                                    with self.db.get_connection() as conn:
                                        with conn.cursor() as cursor:
                                            cursor.execute("""
                                                SELECT id FROM players 
                                                WHERE LOWER(name) = LOWER(%s) AND team_id = %s
                                            """, (injury_data['player_name'], team['id']))
                                            player = cursor.fetchone()
                                    
                                    if player:
                                        self.db.update_player_status(
                                            player_id=player['id'],
                                            status_type=injury_data.get('injury_type', 'injury'),
                                            description=injury_data.get('injury_description', 'Injured'),
                                            expected_return_date=injury_data.get('return_date'),
                                            source_url=f"https://www.transfermarkt.com/verein/verletztenliste/verein/{team['transfermarkt_id']}"
                                        )
                                
                                logger.debug(f"Updated {len(injuries)} injuries for {team['name']}")
                                time.sleep(1)  # Rate limiting
                                
                            except Exception as e:
                                logger.error(f"Error updating injuries for {team['name']}: {e}")
                                continue
                                
                except Exception as e:
                    logger.error(f"Error updating injuries for league {league_info['name']}: {e}")
                    continue
            
            logger.info("✅ Injuries and suspensions update completed")
            
        except Exception as e:
            logger.error(f"❌ Error updating injuries and suspensions: {e}")
    
    def update_matches_only(self):
        """Update only match data for all leagues (hourly) with improved error handling"""
        logger.info("Starting hourly match data update")
        
        try:
            for league_key, league_info in LEAGUES.items():
                try:
                    league_db = self.db.get_league_by_transfermarkt_id(league_info['transfermarkt_id'])
                    if league_db:
                        self.update_matches(league_db['id'], league_info)
                except Exception as e:
                    logger.error(f"❌ Failed to update matches for {league_info['name']}: {e}")
                    continue
            
            logger.info("Hourly match data update completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Critical error in hourly match data update: {e}")
    
    def update_league_data(self, league_key, league_info):
        """Update data for a specific league"""
        try:
            logger.info(f"Updating data for {league_info['name']}")
            
            league_db = self.db.get_league_by_transfermarkt_id(league_info['transfermarkt_id'])
            if not league_db:
                league_id = self.db.insert_league(
                    name=league_info['name'],
                    transfermarkt_id=league_info['transfermarkt_id'],
                    season=league_info['season']
                )
            else:
                league_id = league_db['id']
            
            self.update_matches(league_id, league_info)
            
            self.update_teams_and_players(league_id, league_info)
            
            self.update_player_status(league_id)
            
            self.update_news_data(league_id)
            
            self.update_lineup_predictions(league_id)
            
            logger.info(f"Data update completed for {league_info['name']}")
            
        except Exception as e:
            logger.error(f"Error updating data for {league_info['name']}: {e}")
    
    def update_matches(self, league_id, league_info):
        """Update match data for a league with improved per-league error handling"""
        start_time = time.time()
        try:
            logger.info(f"🏆 Updating matches for {league_info['name']}...")
            
            matches = self.transfermarkt_scraper.scrape_league_matches(
                league_info['transfermarkt_id'], 
                league_info['season']
            )
            
            if not matches:
                logger.warning(f"⚠️ No matches found for {league_info['name']} - scraper may have failed, but continuing with other leagues")
                return
            
            matches_processed = 0
            matches_updated = 0
            for match_data in matches:
                try:
                    home_team_id = self._get_or_create_team(
                        match_data['home_team_name'],
                        league_id,
                        match_data['home_team_transfermarkt_id']
                    )
                    
                    away_team_id = self._get_or_create_team(
                        match_data['away_team_name'],
                        league_id,
                        match_data['away_team_transfermarkt_id']
                    )
                    
                    if home_team_id and away_team_id:
                        match_id = self.db.insert_match(
                            home_team_id=home_team_id,
                            away_team_id=away_team_id,
                            league_id=league_id,
                            match_date=match_data['match_date'],
                            matchday=match_data['matchday'],
                            transfermarkt_id=match_data['transfermarkt_match_id']
                        )
                        if match_id:
                            matches_updated += 1
                    matches_processed += 1
                except Exception as e:
                    logger.error(f"❌ Error processing match {match_data.get('home_team_name', 'Unknown')} vs {match_data.get('away_team_name', 'Unknown')} in {league_info['name']}: {e}")
                    continue
            
            duration = time.time() - start_time
            logger.info(f"✅ {league_info['name']}: {matches_updated}/{matches_processed} matches updated in {duration:.1f}s")
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ Failed to update matches for {league_info['name']} after {duration:.1f}s: {e}")
    
    def update_teams_and_players(self, league_id, league_info):
        """Update team squads and player data"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, transfermarkt_id, name 
                        FROM teams 
                        WHERE league_id = %s
                    """, (league_id,))
                    teams = cursor.fetchall()
            
            for team in teams:
                try:
                    players = self.transfermarkt_scraper.scrape_team_squad(team['transfermarkt_id'])
                    
                    for player_data in players:
                        self.db.insert_player(
                            name=player_data['name'],
                            team_id=team['id'],
                            position=player_data['position'],
                            transfermarkt_id=player_data['transfermarkt_id'],
                            jersey_number=player_data.get('jersey_number'),
                            market_value=player_data.get('market_value')
                        )
                    
                    logger.info(f"Updated {len(players)} players for {team['name']}")
                    
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error updating players for team {team['name']}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error updating teams and players for league {league_id}: {e}")
    
    def update_player_status(self, league_id):
        """Update player injury and suspension status"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, transfermarkt_id, name 
                        FROM teams 
                        WHERE league_id = %s
                    """, (league_id,))
                    teams = cursor.fetchall()
            
            for team in teams:
                try:
                    injuries = self.transfermarkt_scraper.scrape_player_injuries(team['transfermarkt_id'])
                    
                    for injury_data in injuries:
                        with self.db.get_connection() as conn:
                            with conn.cursor() as cursor:
                                cursor.execute("""
                                    SELECT id FROM players 
                                    WHERE transfermarkt_id = %s AND team_id = %s
                                """, (injury_data['player_transfermarkt_id'], team['id']))
                                player = cursor.fetchone()
                        
                        if player:
                            self.db.update_player_status(
                                player_id=player['id'],
                                status_type=injury_data['status_type'],
                                description=injury_data['injury_description'],
                                source_url=f"https://www.transfermarkt.com/verein/verletztenliste/verein/{team['transfermarkt_id']}"
                            )
                    
                    logger.info(f"Updated {len(injuries)} injury statuses for {team['name']}")
                    
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error updating player status for team {team['name']}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error updating player status for league {league_id}: {e}")
    
    def update_news_data(self, league_id):
        """Update news and social media data"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, name FROM teams WHERE league_id = %s
                    """, (league_id,))
                    teams = cursor.fetchall()
            
            for team in teams[:5]:  # Limit to 5 teams per update to avoid rate limits
                try:
                    team_name = team['name']
                    
                    with self.db.get_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("""
                                SELECT name FROM players 
                                WHERE team_id = %s 
                                ORDER BY market_value DESC NULLS LAST
                                LIMIT 10
                            """, (team['id'],))
                            players = cursor.fetchall()
                    
                    player_names = [p['name'] for p in players]
                    
                    bbc_news = self.news_scraper.scrape_bbc_football_news(team_name)
                    
                    twitter_mentions = self.news_scraper.scrape_twitter_mentions(team_name, player_names)
                    
                    all_mentions = bbc_news + twitter_mentions
                    for mention in all_mentions:
                        with self.db.get_connection() as conn:
                            with conn.cursor() as cursor:
                                cursor.execute("""
                                    INSERT INTO news_mentions 
                                    (team_id, source_type, source_url, author, content, published_at)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                    ON CONFLICT DO NOTHING
                                """, (
                                    team['id'],
                                    mention.get('source', 'unknown'),
                                    mention.get('url'),
                                    mention.get('author'),
                                    mention.get('content', mention.get('headline', '')),
                                    mention.get('published_at', datetime.now())
                                ))
                                conn.commit()
                    
                    logger.info(f"Updated {len(all_mentions)} news mentions for {team_name}")
                    
                    time.sleep(3)
                    
                except Exception as e:
                    logger.error(f"Error updating news data for team {team_name}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error updating news data for league {league_id}: {e}")
    
    def update_lineup_predictions(self, league_id):
        """Update lineup predictions for upcoming matches in a specific league"""
        try:
            matches = self.db.get_upcoming_matches(league_id)
            
            for match in matches[:5]:  # Limit to 5 matches per update
                try:
                    for team_id in [match['home_team_id'], match['away_team_id']]:
                        prediction = self.predictor.predict_lineup(match['id'], team_id)
                        if prediction:
                            logger.info(f"Updated lineup prediction for team {team_id} in match {match['id']}")
                    
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error updating lineup predictions for match {match['id']}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error updating lineup predictions for league {league_id}: {e}")
    
    def update_all_lineup_predictions(self):
        """Update lineup predictions for all upcoming matches across all leagues (every 5 hours)"""
        logger.info("🔄 Starting background lineup prediction generation for all leagues...")
        
        try:
            prediction_count = 0
            
            for league_key, league_info in LEAGUES.items():
                try:
                    league_db = self.db.get_league_by_transfermarkt_id(league_info['transfermarkt_id'])
                    if not league_db:
                        logger.warning(f"League not found in database: {league_info['name']}")
                        continue
                    
                    logger.info(f"Generating predictions for {league_info['name']}...")
                    
                    matches = self.db.get_next_matchday_matches(league_db['id'])
                    
                    for match in matches:
                        try:
                            for team_id in [match['home_team_id'], match['away_team_id']]:
                                existing_prediction = self.db.get_lineup_prediction(match['id'], team_id)
                                
                                if not existing_prediction:
                                    prediction = self.predictor.predict_lineup(match['id'], team_id)
                                    if prediction:
                                        prediction_count += 1
                                        logger.info(f"✅ Generated prediction for team {team_id} in match {match['id']}")
                                else:
                                    logger.debug(f"Prediction already exists for team {team_id} in match {match['id']}")
                            
                            time.sleep(0.5)
                            
                        except Exception as e:
                            logger.error(f"Error generating prediction for match {match['id']}: {e}")
                            continue
                    
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error processing league {league_info['name']}: {e}")
                    continue
            
            logger.info(f"✅ Background prediction generation completed. Generated {prediction_count} new predictions.")
            
        except Exception as e:
            logger.error(f"❌ Critical error in background prediction generation: {e}")
    
    def generate_initial_predictions(self):
        """Generate initial predictions for all upcoming matches (run once at startup)"""
        logger.info("🚀 Generating initial lineup predictions for all upcoming matches...")
        
        try:
            self.update_all_lineup_predictions()
            logger.info("✅ Initial prediction generation completed")
            
        except Exception as e:
            logger.error(f"❌ Error in initial prediction generation: {e}")
    
    def _get_or_create_team(self, team_name, league_id, transfermarkt_id):
        """Get existing team or create new one"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT id FROM teams 
                        WHERE transfermarkt_id = %s AND league_id = %s
                    """, (transfermarkt_id, league_id))
                    team = cursor.fetchone()
            
            if team:
                return team['id']
            else:
                return self.db.insert_team(team_name, league_id, transfermarkt_id)
                
        except Exception as e:
            logger.error(f"Error getting or creating team {team_name}: {e}")
            return None
    
    def update_squad_data(self):
        """Update squad data for all teams"""
        try:
            logger.info("🔄 Starting squad data update...")
            
            from fetchers.squad_parser import SquadParser
            from fetchers.logo_scraper import LogoScraper
            
            squad_parser = SquadParser()
            logo_scraper = LogoScraper()
            
            logo_scraper.update_all_team_logos()
            
            teams = self.db.get_all_teams()
            for team in teams:
                if team['transfermarkt_id']:
                    try:
                        squad_parser.update_team_squad(team['id'], team['transfermarkt_id'])
                        time.sleep(2)
                    except Exception as e:
                        logger.error(f"Error updating squad for {team['name']}: {e}")
                        continue
            
            logger.info("✅ Squad data update completed")
            
        except Exception as e:
            logger.error(f"❌ Error in squad data update: {e}")
