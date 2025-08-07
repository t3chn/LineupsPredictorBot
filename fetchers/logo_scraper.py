#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from database.models import DatabaseManager
import logging
import time
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LogoScraper:
    def __init__(self):
        self.db = DatabaseManager()
        self.driver = None
        
    def init_driver(self):
        """Initialize headless Chrome driver"""
        if self.driver:
            return
            
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        
    def close_driver(self):
        """Close the driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def scrape_team_logo(self, team_transfermarkt_id):
        """Scrape team logo from Transfermarkt"""
        try:
            self.init_driver()
            
            url = f"https://www.transfermarkt.com/team/startseite/verein/{team_transfermarkt_id}"
            logger.info(f"🔍 Scraping logo from: {url}")
            
            self.driver.get(url)
            time.sleep(2)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            logo_img = soup.find('img', {'class': 'dataBild'})
            if logo_img:
                logo_url = logo_img.get('src')
                if logo_url and logo_url.startswith('//'):
                    logo_url = 'https:' + logo_url
                elif logo_url and logo_url.startswith('/'):
                    logo_url = 'https://www.transfermarkt.com' + logo_url
                
                logger.info(f"✅ Found logo: {logo_url}")
                return logo_url
            
            header_logo = soup.find('div', {'class': 'dataHeader'})
            if header_logo:
                logo_img = header_logo.find('img')
                if logo_img:
                    logo_url = logo_img.get('src')
                    if logo_url and logo_url.startswith('//'):
                        logo_url = 'https:' + logo_url
                    elif logo_url and logo_url.startswith('/'):
                        logo_url = 'https://www.transfermarkt.com' + logo_url
                    
                    logger.info(f"✅ Found header logo: {logo_url}")
                    return logo_url
            
            logger.warning(f"No logo found for team {team_transfermarkt_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error scraping team logo: {e}")
            return None
        finally:
            self.close_driver()
    
    def update_team_logo(self, team_id, team_transfermarkt_id):
        """Update logo for a specific team"""
        try:
            logo_url = self.scrape_team_logo(team_transfermarkt_id)
            
            if logo_url:
                with self.db.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            UPDATE teams SET logo_url = %s WHERE id = %s
                        """, (logo_url, team_id))
                        conn.commit()
                
                logger.info(f"✅ Updated logo for team {team_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error updating team logo: {e}")
            return False
    
    def update_all_team_logos(self):
        """Update logos for all teams"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, name, transfermarkt_id 
                        FROM teams 
                        WHERE transfermarkt_id IS NOT NULL 
                        AND (logo_url IS NULL OR logo_url = '')
                    """)
                    teams = cursor.fetchall()
            
            logger.info(f"🔄 Updating logos for {len(teams)} teams...")
            
            for team in teams:
                try:
                    logger.info(f"📸 Processing {team['name']}...")
                    self.update_team_logo(team['id'], team['transfermarkt_id'])
                    time.sleep(1)  # Be respectful to the server
                except Exception as e:
                    logger.error(f"❌ Error processing team {team['name']}: {e}")
                    continue
            
            logger.info("🎉 Logo update completed!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating all team logos: {e}")
            return False
    
    def get_fallback_emoji(self, team_name):
        """Get fallback emoji for teams without logos"""
        team_emojis = {
            'Liverpool': '🔴',
            'Liverpool FC': '🔴',
            'Manchester United': '🔴',
            'Manchester City': '🔵',
            'Arsenal': '🔴',
            'Arsenal FC': '🔴',
            'Chelsea': '🔵',
            'Chelsea FC': '🔵',
            'Tottenham': '⚪',
            'Newcastle': '⚫',
            'Brighton': '🔵',
            'Brighton & Hove Albion': '🔵',
            'Aston Villa': '🟣',
            'West Ham': '⚫',
            'Everton': '🔵',
            'Everton FC': '🔵',
            'Leeds United': '⚪',
            'AFC Bournemouth': '🔴',
            'Brentford FC': '🔴',
            'Nottingham Forest': '🔴',
            'Crystal Palace': '🔵',
            'Fulham': '⚪',
            'Wolverhampton Wanderers': '🟠',
            'Burnley': '🔴',
            'Sheffield United': '🔴',
            'Luton Town': '🟠',
            
            'Real Madrid': '⚪',
            'Barcelona': '🔵',
            'FC Barcelona': '🔵',
            'Atletico Madrid': '🔴',
            'Sevilla': '🔴',
            'Valencia': '🟠',
            'Real Sociedad': '🔵',
            'Athletic Bilbao': '🔴',
            'Villarreal': '🟡',
            'Real Betis': '🟢',
            'RCD Espanyol Barcelona': '🔵',
            'Getafe': '🔵',
            'Osasuna': '🔴',
            'Celta Vigo': '🔵',
            'Mallorca': '🔴',
            'Las Palmas': '🟡',
            'Cadiz': '🟡',
            'Granada': '🔴',
            'Almeria': '🔴',
            'Rayo Vallecano': '🔴',
            
            'Juventus': '⚫',
            'Juventus FC': '⚫',
            'AC Milan': '🔴',
            'Inter Milan': '🔵',
            'AS Roma': '🟡',
            'Napoli': '🔵',
            'Lazio': '🔵',
            'Atalanta': '🔵',
            'ACF Fiorentina': '🟣',
            'Bologna FC 1909': '🔴',
            'Torino': '🔴',
            'Udinese': '⚫',
            'Sassuolo': '🟢',
            'Hellas Verona': '🟡',
            'Genoa': '🔴',
            'Cagliari': '🔴',
            'Lecce': '🟡',
            'Frosinone': '🟡',
            'Empoli': '🔵',
            'Monza': '🔴',
            
            'Bayern Munich': '🔴',
            'Borussia Dortmund': '🟡',
            'Bor. Dortmund': '🟡',
            'RB Leipzig': '🔴',
            'Bayer Leverkusen': '🔴',
            'Borussia Mönchengladbach': '⚫',
            'VfL Wolfsburg': '🟢',
            'Eintracht Frankfurt': '🔴',
            'SC Freiburg': '🔴',
            '1.FC Union Berlin': '🔴',
            '1.FC Köln': '🔴',
            '1.FSV Mainz 05': '🔴',
            '1.FC Heidenheim 1846': '🔴',
            'VfB Stuttgart': '🔴',
            'TSG Hoffenheim': '🔵',
            'FC Augsburg': '🔴',
            'SV Darmstadt 98': '🔵',
            'Werder Bremen': '🟢',
            
            'PSG': '🔵',
            'Marseille': '🔵',
            'Lyon': '🔵',
            'Monaco': '🔴',
            'Lille': '🔴',
            'Nice': '🔴',
            'Rennes': '🔴',
            'Strasbourg': '🔵',
            'Lens': '🟡',
            'Nantes': '🟡',
            'Montpellier': '🔵',
            'Reims': '🔴',
            'Toulouse': '🟣',
            'Brest': '🔴',
            'Le Havre': '🔵',
            'Metz': '🔴',
            'Lorient': '🟠',
            'Clermont': '🔴',
            
            'Spartak Moscow': '🔴⚪',
            'Zenit': '🔵⚪',
            'CSKA Moscow': '🔴',
            'Dynamo Moscow': '🔵',
            'Lokomotiv Moscow': '🟢',
            'Rubin Kazan': '🟢',
            'Krasnodar': '🟢',
            'Rostov': '🟡',
            'Akhmat Grozny': '🟢',
            'Sochi': '🔵',
            'Ural': '🟠',
            'Orenburg': '🔴',
            'Fakel Voronezh': '🔴',
            'Baltika': '🔵',
            'Nizhny Novgorod': '🔵',
            'Khimki': '🟡'
        }
        
        return team_emojis.get(team_name, '⚽')

if __name__ == "__main__":
    scraper = LogoScraper()
    scraper.update_all_team_logos()
