import psycopg2
from psycopg2.extras import RealDictCursor
import json
import logging
from datetime import datetime
from config import DATABASE_URL

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.connection_string = DATABASE_URL
        
    def get_connection(self):
        return psycopg2.connect(self.connection_string, cursor_factory=RealDictCursor)
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS leagues (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        transfermarkt_id VARCHAR(10) NOT NULL,
                        season VARCHAR(10) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS teams (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        league_id INTEGER REFERENCES leagues(id),
                        transfermarkt_id VARCHAR(20),
                        logo_url TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS club_aliases (
                        id SERIAL PRIMARY KEY,
                        team_id INTEGER REFERENCES teams(id),
                        alias_name VARCHAR(100) NOT NULL,
                        alias_type VARCHAR(20) NOT NULL, -- 'official', 'short', 'twitter', 'localized'
                        language_code VARCHAR(5), -- 'en', 'ru', 'de', 'fr', 'es', 'it', 'uk'
                        source VARCHAR(50), -- 'transfermarkt', 'twitter', 'sofascore', etc.
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS matches (
                        id SERIAL PRIMARY KEY,
                        home_team_id INTEGER REFERENCES teams(id),
                        away_team_id INTEGER REFERENCES teams(id),
                        league_id INTEGER REFERENCES leagues(id),
                        match_date TIMESTAMP NOT NULL,
                        matchday INTEGER NOT NULL,
                        transfermarkt_id VARCHAR(20) NOT NULL,
                        status VARCHAR(20) DEFAULT 'scheduled',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS players (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        team_id INTEGER REFERENCES teams(id),
                        position VARCHAR(20) NOT NULL,
                        transfermarkt_id VARCHAR(20),
                        jersey_number INTEGER,
                        market_value BIGINT,
                        age INTEGER,
                        nationality VARCHAR(50),
                        contract_end_year INTEGER,
                        minutes_played INTEGER DEFAULT 0,
                        games_started INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS injuries (
                        id SERIAL PRIMARY KEY,
                        player_id INTEGER REFERENCES players(id),
                        injury_name VARCHAR(200) NOT NULL,
                        injury_start_date DATE,
                        expected_return_date DATE,
                        injury_type VARCHAR(50), -- 'injury', 'illness', 'suspension', 'personal'
                        severity VARCHAR(20), -- 'minor', 'moderate', 'major'
                        source_url TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS player_status (
                        id SERIAL PRIMARY KEY,
                        player_id INTEGER REFERENCES players(id),
                        status_type VARCHAR(20) NOT NULL, -- 'injury', 'suspension', 'illness', 'personal'
                        description TEXT,
                        start_date DATE,
                        expected_return_date DATE,
                        severity VARCHAR(20), -- 'minor', 'moderate', 'major'
                        source_url TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS lineup_predictions (
                        id SERIAL PRIMARY KEY,
                        match_id INTEGER REFERENCES matches(id),
                        team_id INTEGER REFERENCES teams(id),
                        formation VARCHAR(10) NOT NULL,
                        predicted_lineup JSONB NOT NULL, -- Array of player IDs with positions
                        alternative_players JSONB, -- Array of alternative players with probabilities
                        confidence_score FLOAT,
                        reasoning TEXT,
                        sources JSONB, -- Array of source URLs
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS news_mentions (
                        id SERIAL PRIMARY KEY,
                        player_id INTEGER REFERENCES players(id),
                        team_id INTEGER REFERENCES teams(id),
                        match_id INTEGER REFERENCES matches(id),
                        source_type VARCHAR(20) NOT NULL, -- 'twitter', 'news', 'transfermarkt'
                        source_url TEXT,
                        author VARCHAR(100),
                        content TEXT NOT NULL,
                        sentiment VARCHAR(20), -- 'positive', 'negative', 'neutral'
                        relevance_score FLOAT,
                        published_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        id SERIAL PRIMARY KEY,
                        telegram_user_id BIGINT NOT NULL,
                        current_league_id INTEGER REFERENCES leagues(id),
                        current_match_id INTEGER REFERENCES matches(id),
                        current_team_id INTEGER REFERENCES teams(id),
                        session_data JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(telegram_user_id)
                    )
                """)
                
                conn.commit()
    
    def insert_league(self, name, transfermarkt_id, season):
        """Insert a league into the database"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO leagues (name, transfermarkt_id, season)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """, (name, transfermarkt_id, season))
                result = cursor.fetchone()
                conn.commit()
                return result['id'] if result else None
    
    def get_league_by_transfermarkt_id(self, transfermarkt_id):
        """Get league by transfermarkt ID (returns most recent if duplicates exist)"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM leagues 
                    WHERE transfermarkt_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (transfermarkt_id,))
                return cursor.fetchone()
    
    def get_or_create_team(self, team_name, league_id, transfermarkt_id=None):
        """Get existing team or create new one"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id FROM teams 
                    WHERE name = %s AND league_id = %s
                """, (team_name, league_id))
                team = cursor.fetchone()
                
                if team:
                    return team['id']
                
                return self.insert_team(team_name, league_id, transfermarkt_id)
    
    def get_all_leagues(self):
        """Get all leagues"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM leagues ORDER BY name")
                return cursor.fetchall()
    
    def insert_team(self, name, league_id, transfermarkt_id, logo_url=None):
        """Insert a team into the database"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO teams (name, league_id, transfermarkt_id, logo_url)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """, (name, league_id, transfermarkt_id, logo_url))
                result = cursor.fetchone()
                conn.commit()
                return result['id'] if result else None
    
    def insert_club_alias(self, team_id, alias_name, alias_type, language_code=None, source=None):
        """Insert a club alias"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO club_aliases (team_id, alias_name, alias_type, language_code, source)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """, (team_id, alias_name, alias_type, language_code, source))
                result = cursor.fetchone()
                conn.commit()
                return result['id'] if result else None
    
    def get_team_aliases(self, team_id):
        """Get all aliases for a team"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM club_aliases WHERE team_id = %s
                """, (team_id,))
                return cursor.fetchall()
    
    def find_team_by_alias(self, alias_name, league_id=None):
        """Find team by any of its aliases"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                if league_id:
                    cursor.execute("""
                        SELECT t.* FROM teams t
                        JOIN club_aliases ca ON t.id = ca.team_id
                        WHERE LOWER(ca.alias_name) = LOWER(%s) AND t.league_id = %s
                        LIMIT 1
                    """, (alias_name, league_id))
                else:
                    cursor.execute("""
                        SELECT t.* FROM teams t
                        JOIN club_aliases ca ON t.id = ca.team_id
                        WHERE LOWER(ca.alias_name) = LOWER(%s)
                        LIMIT 1
                    """, (alias_name,))
                return cursor.fetchone()
    
    def insert_match(self, home_team_id, away_team_id, league_id, match_date, matchday, transfermarkt_id):
        """Insert or update a match (preserve existing data as requested)"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id FROM matches 
                    WHERE home_team_id = %s AND away_team_id = %s 
                    AND league_id = %s AND matchday = %s
                """, (home_team_id, away_team_id, league_id, matchday))
                
                existing_match = cursor.fetchone()
                
                if existing_match:
                    cursor.execute("""
                        UPDATE matches 
                        SET match_date = %s, transfermarkt_id = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        RETURNING id
                    """, (match_date, transfermarkt_id, existing_match['id']))
                    result = cursor.fetchone()
                    logger.debug(f"Updated existing match {result['id']}")
                else:
                    cursor.execute("""
                        INSERT INTO matches (home_team_id, away_team_id, league_id, match_date, matchday, transfermarkt_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (home_team_id, away_team_id, league_id, match_date, matchday, transfermarkt_id))
                    result = cursor.fetchone()
                    logger.debug(f"Inserted new match {result['id']}")
                
                conn.commit()
                return result['id'] if result else None
    
    def get_upcoming_matches(self, league_id, matchday=None):
        """Get upcoming matches for a league, optionally filtered by matchday"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                if matchday:
                    cursor.execute("""
                        SELECT m.*, 
                               ht.name as home_team_name, ht.logo_url as home_team_logo,
                               at.name as away_team_name, at.logo_url as away_team_logo
                        FROM matches m
                        JOIN teams ht ON m.home_team_id = ht.id
                        JOIN teams at ON m.away_team_id = at.id
                        WHERE m.league_id = %s 
                        AND m.matchday = %s
                        AND m.match_date > NOW()
                        AND m.status = 'scheduled'
                        ORDER BY m.match_date ASC
                    """, (league_id, matchday))
                else:
                    cursor.execute("""
                        SELECT m.*, 
                               ht.name as home_team_name, ht.logo_url as home_team_logo,
                               at.name as away_team_name, at.logo_url as away_team_logo
                        FROM matches m
                        JOIN teams ht ON m.home_team_id = ht.id
                        JOIN teams at ON m.away_team_id = at.id
                        WHERE m.league_id = %s 
                        AND m.match_date > NOW()
                        AND m.status = 'scheduled'
                        ORDER BY m.match_date ASC
                    """, (league_id,))
                return cursor.fetchall()
    
    def get_next_matchday_matches(self, league_id):
        """Get matches from the next upcoming matchday"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT MIN(matchday) as next_matchday
                    FROM matches 
                    WHERE league_id = %s 
                    AND match_date > NOW()
                    AND status = 'scheduled'
                """, (league_id,))
                result = cursor.fetchone()
                
                if result and result['next_matchday']:
                    next_matchday = result['next_matchday']
                    
                    cursor.execute("""
                        SELECT m.*, 
                               ht.name as home_team_name, ht.logo_url as home_team_logo,
                               at.name as away_team_name, at.logo_url as away_team_logo
                        FROM matches m
                        JOIN teams ht ON m.home_team_id = ht.id
                        JOIN teams at ON m.away_team_id = at.id
                        WHERE m.league_id = %s 
                        AND m.matchday = %s
                        AND m.match_date > NOW()
                        AND m.status = 'scheduled'
                        ORDER BY m.match_date ASC
                    """, (league_id, next_matchday))
                    return cursor.fetchall()
                
                return []
    
    def get_league_teams_count(self, league_id):
        """Get number of teams in a league"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) as team_count FROM teams WHERE league_id = %s
                """, (league_id,))
                result = cursor.fetchone()
                return result['team_count'] if result else 0
    
    def insert_player(self, name, team_id, position, transfermarkt_id, jersey_number=None, market_value=None, age=None, nationality=None, contract_end_year=None):
        """Insert a player into the database"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO players (name, team_id, position, transfermarkt_id, jersey_number, market_value, age, nationality, contract_end_year)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """, (name, team_id, position, transfermarkt_id, jersey_number, market_value, age, nationality, contract_end_year))
                result = cursor.fetchone()
                conn.commit()
                return result['id'] if result else None
    
    def insert_injury(self, player_id, injury_name, injury_start_date=None, expected_return_date=None, injury_type='injury', severity='moderate', source_url=None):
        """Insert player injury information"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE injuries SET is_active = FALSE 
                    WHERE player_id = %s AND is_active = TRUE
                """, (player_id,))
                
                cursor.execute("""
                    INSERT INTO injuries (player_id, injury_name, injury_start_date, expected_return_date, injury_type, severity, source_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (player_id, injury_name, injury_start_date, expected_return_date, injury_type, severity, source_url))
                result = cursor.fetchone()
                conn.commit()
                return result['id'] if result else None
    
    def get_player_injuries(self, player_id):
        """Get active injuries for a player"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM injuries 
                    WHERE player_id = %s AND is_active = TRUE
                    ORDER BY created_at DESC
                """, (player_id,))
                return cursor.fetchall()
    
    def get_team_injured_players(self, team_id):
        """Get all injured players for a team"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT p.*, i.injury_name, i.expected_return_date, i.injury_type, i.severity
                    FROM players p
                    JOIN injuries i ON p.id = i.player_id
                    WHERE p.team_id = %s 
                    AND (i.expected_return_date IS NULL OR i.expected_return_date > CURRENT_DATE)
                    AND i.actual_return_date IS NULL
                    ORDER BY i.expected_return_date ASC
                """, (team_id,))
                return cursor.fetchall()
    
    def update_player_status(self, player_id, status_type, description, start_date=None, expected_return_date=None, severity=None, source_url=None):
        """Update player status (injury, suspension, etc.)"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE player_status 
                    SET is_active = FALSE 
                    WHERE player_id = %s AND status_type = %s AND is_active = TRUE
                """, (player_id, status_type))
                
                cursor.execute("""
                    INSERT INTO player_status (player_id, status_type, description, start_date, expected_return_date, severity, source_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (player_id, status_type, description, start_date, expected_return_date, severity, source_url))
                result = cursor.fetchone()
                conn.commit()
                return result['id'] if result else None
    
    def get_team_players(self, team_id):
        """Get all players for a team"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT p.*, 
                           COALESCE(
                               JSON_AGG(
                                   JSON_BUILD_OBJECT(
                                       'status_type', ps.status_type,
                                       'description', ps.description,
                                       'severity', ps.severity,
                                       'expected_return_date', ps.expected_return_date
                                   )
                               ) FILTER (WHERE ps.is_active = TRUE), 
                               '[]'
                           ) as current_status
                    FROM players p
                    LEFT JOIN player_status ps ON p.id = ps.player_id AND ps.is_active = TRUE
                    WHERE p.team_id = %s
                    GROUP BY p.id
                    ORDER BY p.position, p.jersey_number
                """, (team_id,))
                return cursor.fetchall()
    
    def save_lineup_prediction(self, match_id, team_id, formation, predicted_lineup, alternative_players=None, confidence_score=None, reasoning=None, sources=None):
        """Save lineup prediction"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM lineup_predictions 
                    WHERE match_id = %s AND team_id = %s
                """, (match_id, team_id))
                
                cursor.execute("""
                    INSERT INTO lineup_predictions (match_id, team_id, formation, predicted_lineup, alternative_players, confidence_score, reasoning, sources)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (match_id, team_id, json.dumps(formation), json.dumps(predicted_lineup), 
                      json.dumps(alternative_players) if alternative_players else None,
                      confidence_score, reasoning, json.dumps(sources) if sources else None))
                result = cursor.fetchone()
                conn.commit()
                return result['id'] if result else None
    
    def get_lineup_prediction(self, match_id, team_id):
        """Get lineup prediction for a match and team"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM lineup_predictions 
                    WHERE match_id = %s AND team_id = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, (match_id, team_id))
                return cursor.fetchone()
    
    def update_user_session(self, telegram_user_id, **kwargs):
        """Update user session data"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                update_fields = []
                values = []
                for key, value in kwargs.items():
                    if key in ['current_league_id', 'current_match_id', 'current_team_id', 'session_data']:
                        update_fields.append(f"{key} = %s")
                        values.append(value)
                
                if update_fields:
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    values.append(telegram_user_id)
                    
                    cursor.execute(f"""
                        INSERT INTO user_sessions (telegram_user_id, {', '.join(kwargs.keys())})
                        VALUES (%s, {', '.join(['%s'] * len(kwargs))})
                        ON CONFLICT (telegram_user_id) DO UPDATE SET
                            {', '.join(update_fields)}
                    """, [telegram_user_id] + list(kwargs.values()) + values[:-1])
                    conn.commit()
    
    def get_user_session(self, telegram_user_id):
        """Get user session data"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM user_sessions WHERE telegram_user_id = %s
                """, (telegram_user_id,))
                return cursor.fetchone()
    
    def insert_player_status(self, player_id, status_type, description, expected_return=None, source_url=None):
        """Insert player status for injury/suspension tracking"""
        return self.update_player_status(player_id, status_type, description, 
                                       expected_return_date=expected_return, source_url=source_url)
    
    def get_all_teams(self):
        """Get all teams"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM teams ORDER BY name")
                return cursor.fetchall()
    
    def update_team_logo(self, team_id, logo_url):
        """Update team logo URL"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE teams SET logo_url = %s WHERE id = %s
                """, (logo_url, team_id))
                conn.commit()
                return True
    
    def find_team_by_name(self, team_name):
        """Find team by exact name match"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM teams WHERE LOWER(name) = LOWER(%s)
                """, (team_name,))
                return cursor.fetchone()
    
    def find_team_by_alias(self, alias, league_id=None):
        """Find team by alias"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                if league_id:
                    cursor.execute("""
                        SELECT t.* FROM teams t
                        JOIN club_aliases ca ON t.id = ca.team_id
                        WHERE LOWER(ca.alias_name) = LOWER(%s) AND t.league_id = %s
                        LIMIT 1
                    """, (alias, league_id))
                else:
                    cursor.execute("""
                        SELECT t.* FROM teams t
                        JOIN club_aliases ca ON t.id = ca.team_id
                        WHERE LOWER(ca.alias_name) = LOWER(%s)
                        LIMIT 1
                    """, (alias,))
                return cursor.fetchone()
    
    def get_player_injuries(self, player_id):
        """Get current injuries for a player"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM injuries 
                    WHERE player_id = %s 
                    AND (actual_return_date IS NULL OR actual_return_date > CURRENT_DATE)
                    ORDER BY created_at DESC
                """, (player_id,))
                return cursor.fetchall()
    
    def get_next_matchday_matches(self, league_id):
        """Get matches for the next matchday in a league"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT MIN(matchday) as next_matchday
                    FROM matches 
                    WHERE league_id = %s 
                    AND match_date >= CURRENT_DATE
                """, (league_id,))
                result = cursor.fetchone()
                
                if not result or not result['next_matchday']:
                    return []
                
                next_matchday = result['next_matchday']
                
                cursor.execute("""
                    SELECT m.*, 
                           ht.name as home_team_name, ht.logo_url as home_team_logo,
                           at.name as away_team_name, at.logo_url as away_team_logo
                    FROM matches m
                    JOIN teams ht ON m.home_team_id = ht.id
                    JOIN teams at ON m.away_team_id = at.id
                    WHERE m.league_id = %s AND m.matchday = %s
                    AND m.match_date >= CURRENT_DATE
                    ORDER BY m.match_date, m.match_time
                """, (league_id, next_matchday))
                return cursor.fetchall()
