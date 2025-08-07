import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

class TransfermarktScraper:
    def __init__(self):
        self.base_url = "https://www.transfermarkt.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def get_driver(self):
        """Get Selenium WebDriver for JavaScript-heavy pages with maximum stability"""
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--window-size=1280,720")
        chrome_options.add_argument("--memory-pressure-off")
        chrome_options.add_argument("--max_old_space_size=2048")
        chrome_options.add_argument("--single-process")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        chrome_options.add_argument("--remote-debugging-port=0")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--disable-gpu-logging")
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--disable-crash-reporter")
        chrome_options.add_argument("--disable-in-process-stack-traces")
        chrome_options.add_argument("--disable-dev-tools")
        chrome_options.add_argument("--no-zygote")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument(f"--user-agent={self.headers['User-Agent']}")
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            from selenium.webdriver.chrome.service import Service
            service = Service()
            service.log_path = "/dev/null"
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except:
            driver = webdriver.Chrome(options=chrome_options)
        
        driver.set_page_load_timeout(15)
        driver.implicitly_wait(3)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    
    def scrape_league_matches(self, league_id, season="2025", max_retries=3):
        """Scrape upcoming matches for a league with retry logic"""
        for attempt in range(max_retries):
            driver = None
            try:
                logger.info(f"Scraping matches for league {league_id}, attempt {attempt + 1}/{max_retries}")
                
                current_matchday = self._get_current_matchday(league_id, season)
                
                url = f"{self.base_url}/{self._get_league_slug(league_id)}/gesamtspielplan/wettbewerb/{league_id}?saison_id={season}&spieltagVon={current_matchday}&spieltagBis={current_matchday}"
                
                driver = self.get_driver()
                driver.get(url)
                
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "responsive-table"))
                )
                
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                matches = []
                all_rows = soup.find_all('tr')
                
                current_date_text = None
                current_time_text = None
                
                for row in all_rows:
                    try:
                        match_data, current_date_text, current_time_text = self._parse_match_row_enhanced(
                            row, current_matchday, current_date_text, current_time_text
                        )
                        if match_data:
                            matches.append(match_data)
                    except Exception as e:
                        logger.warning(f"Error parsing match row: {e}")
                        continue
                
                logger.info(f"Successfully scraped {len(matches)} matches for league {league_id}")
                return matches
                
            except Exception as e:
                logger.error(f"Chrome attempt {attempt + 1} failed for league {league_id}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)  # Wait before retry
            finally:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
        
        logger.warning(f"Chrome failed for league {league_id}, trying requests fallback...")
        try:
            return self._scrape_with_requests_fallback(league_id, season)
        except Exception as e:
            logger.error(f"Requests fallback also failed for league {league_id}: {e}")
            return []
    
    def _scrape_with_requests_fallback(self, league_id, season="2025"):
        """Fallback scraping using requests when Chrome fails"""
        try:
            current_matchday = self._get_current_matchday(league_id, season)
            url = f"{self.base_url}/{self._get_league_slug(league_id)}/gesamtspielplan/wettbewerb/{league_id}?saison_id={season}&spieltagVon={current_matchday}&spieltagBis={current_matchday}"
            
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            matches = []
            all_rows = soup.find_all('tr')
            
            current_date_text = None
            current_time_text = None
            
            for row in all_rows:
                try:
                    match_data, current_date_text, current_time_text = self._parse_match_row_enhanced(
                        row, current_matchday, current_date_text, current_time_text
                    )
                    if match_data:
                        matches.append(match_data)
                except Exception as e:
                    logger.warning(f"Error parsing match row in fallback: {e}")
                    continue
            
            logger.info(f"Successfully scraped {len(matches)} matches for league {league_id} with requests fallback")
            return matches
            
        except Exception as e:
            logger.error(f"Requests fallback failed for league {league_id}: {e}")
            return []
    
    def _get_current_matchday(self, league_id, season):
        """Get the current matchday for a league"""
        try:
            url = f"{self.base_url}/{self._get_league_slug(league_id)}/startseite/wettbewerb/{league_id}/plus/?saison_id={season}"
            response = self.session.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            matchday_element = soup.find('select', {'name': 'spieltag'})
            if matchday_element:
                selected_option = matchday_element.find('option', selected=True)
                if selected_option:
                    return int(selected_option.get('value', 1))
            
            return 1  # Default to matchday 1
            
        except Exception as e:
            logger.error(f"Error getting current matchday: {e}")
            return 1
    
    def _get_league_slug(self, league_id):
        """Get league slug for URL construction"""
        league_slugs = {
            'GB1': 'premier-league',
            'ES1': 'primera-division',
            'IT1': 'serie-a',
            'L1': 'bundesliga',
            'FR1': 'ligue-1',
            'RU1': 'premier-liga'
        }
        return league_slugs.get(league_id, 'premier-league')
    
    def _parse_match_row(self, row, matchday):
        """Parse a match row from the table with enhanced HTML parsing"""
        try:
            cells = row.find_all('td')
            if len(cells) < 5:
                return None
            
            date_cell = cells[0]
            time_cell = cells[1] if len(cells) > 1 else None
            
            date_text = date_cell.get_text(strip=True)
            time_text = time_cell.get_text(strip=True) if time_cell else ""
            
            home_team_cell = cells[2]
            home_team_link = home_team_cell.find('a')
            if not home_team_link:
                return None
            
            home_team_name = home_team_link.get_text(strip=True)
            home_team_id = self._extract_team_id(home_team_link.get('href', ''))
            
            away_team_cell = cells[4] if len(cells) > 4 else None
            if not away_team_cell:
                return None
                
            away_team_link = away_team_cell.find('a')
            if not away_team_link:
                return None
                
            away_team_name = away_team_link.get_text(strip=True)
            away_team_id = self._extract_team_id(away_team_link.get('href', ''))
            
            match_datetime = self._parse_match_datetime(date_text, time_text)
            
            result_cell = cells[3] if len(cells) > 3 else None
            match_link = result_cell.find('a') if result_cell else None
            match_id = self._extract_match_id(match_link.get('href', '')) if match_link else None
            
            return {
                'home_team_name': home_team_name,
                'away_team_name': away_team_name,
                'home_team_transfermarkt_id': home_team_id,
                'away_team_transfermarkt_id': away_team_id,
                'match_date': match_datetime,
                'matchday': matchday,
                'transfermarkt_match_id': match_id
            }
            
        except Exception as e:
            logger.error(f"Error parsing match row: {e}")
            return None

    def _parse_match_row_enhanced(self, row, matchday, current_date_text=None, current_time_text=None):
        """Parse a match row with enhanced logic to handle shared date cells"""
        try:
            cells = row.find_all('td')
            if len(cells) < 7:
                return None, current_date_text, current_time_text
            
            home_team_cell = cells[2] if len(cells) > 2 else None
            away_team_cell = cells[6] if len(cells) > 6 else None
            
            if not home_team_cell or not away_team_cell:
                return None, current_date_text, current_time_text
            
            home_team_link = home_team_cell.find('a')
            away_team_link = away_team_cell.find('a')
            
            if not home_team_link or not away_team_link:
                return None, current_date_text, current_time_text
            
            date_cell = cells[0]
            time_cell = cells[1]
            
            date_link = date_cell.find('a')
            if date_link:
                current_date_text = date_link.get_text(strip=True)
                current_time_text = time_cell.get_text(strip=True)
            else:
                time_text_in_cell = time_cell.get_text(strip=True)
                if time_text_in_cell and time_text_in_cell != "":
                    current_time_text = time_text_in_cell
            
            if not current_date_text:
                return None, current_date_text, current_time_text
            
            home_team_name = home_team_link.get_text(strip=True)
            away_team_name = away_team_link.get_text(strip=True)
            
            home_team_id = self._extract_team_id(home_team_link.get('href', ''))
            away_team_id = self._extract_team_id(away_team_link.get('href', ''))
            
            match_datetime = self._parse_match_datetime(current_date_text, current_time_text)
            
            result_cell = cells[4] if len(cells) > 4 else None
            match_link = result_cell.find('a') if result_cell else None
            match_id = self._extract_match_id(match_link.get('href', '')) if match_link else None
            
            return {
                'home_team_name': home_team_name,
                'away_team_name': away_team_name,
                'home_team_transfermarkt_id': home_team_id,
                'away_team_transfermarkt_id': away_team_id,
                'match_date': match_datetime,
                'matchday': matchday,
                'transfermarkt_match_id': match_id
            }, current_date_text, current_time_text
            
        except Exception as e:
            logger.error(f"Error parsing match row: {e}")
            return None, current_date_text, current_time_text
    
    def _extract_team_id(self, href):
        """Extract team ID from href"""
        match = re.search(r'/verein/(\d+)', href)
        return match.group(1) if match else None
    
    def _extract_match_id(self, href):
        """Extract match ID from href"""
        match = re.search(r'/spielbericht/index/spielbericht/(\d+)', href)
        return match.group(1) if match else None
    
    def _parse_match_datetime(self, date_text, time_text):
        """Parse match date and time with enhanced format handling"""
        try:
            current_year = datetime.now().year
            
            if '/' in date_text:
                date_part = date_text.split()[-1] if ' ' in date_text else date_text
                date_parts = date_part.split('/')
                
                if len(date_parts) == 3:
                    month, day, year = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
                    if year < 100:
                        year = 2000 + year if year < 50 else 1900 + year
                else:
                    return datetime.now() + timedelta(days=1)
            elif '.' in date_text:
                date_parts = date_text.split('.')
                if len(date_parts) == 2:
                    day, month = int(date_parts[0]), int(date_parts[1])
                    year = current_year
                elif len(date_parts) == 3:
                    day, month, year = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
                else:
                    return datetime.now() + timedelta(days=1)
            else:
                return datetime.now() + timedelta(days=1)
            
            hour, minute = 15, 0
            if time_text and ':' in time_text:
                time_clean = time_text.replace('PM', '').replace('AM', '').strip()
                if ':' in time_clean:
                    time_parts = time_clean.split(':')
                    if len(time_parts) == 2:
                        hour, minute = int(time_parts[0]), int(time_parts[1])
                        
                        if 'PM' in time_text and hour != 12:
                            hour += 12
                        elif 'AM' in time_text and hour == 12:
                            hour = 0
            
            return datetime(year, month, day, hour, minute)
            
        except Exception as e:
            logger.error(f"Error parsing datetime from '{date_text}' and '{time_text}': {e}")
            return datetime.now() + timedelta(days=1)
    
    def scrape_league_teams(self, league_id, season):
        """Scrape teams from a league, excluding B teams and youth teams"""
        try:
            url = f"https://www.transfermarkt.com/wettbewerb/tabelle/wettbewerb/{league_id}/saison_id/{season}"
            
            driver = self.get_driver()
            driver.get(url)
            time.sleep(5)
            
            teams = []
            seen_teams = set()
            
            team_links = driver.find_elements(By.CSS_SELECTOR, "td.no-border-links.hauptlink a")
            
            for link in team_links:
                try:
                    team_name = link.text.strip()
                    if not team_name:
                        team_name = link.get_attribute("title")
                        if team_name:
                            team_name = team_name.strip()
                    
                    if not team_name or len(team_name) < 3:
                        continue
                    
                    if team_name in seen_teams:
                        continue
                    
                    skip_patterns = [' B ', ' II ', ' U21', ' U19', ' U23', ' U18', 'Youth', 'Reserve', 'Reserves', 'Amateur']
                    end_patterns = [' B', ' II']
                    
                    should_skip = False
                    for pattern in skip_patterns:
                        if pattern in team_name:
                            should_skip = True
                            break
                    
                    if not should_skip:
                        for pattern in end_patterns:
                            if team_name.endswith(pattern):
                                should_skip = True
                                break
                    
                    if should_skip:
                        logger.info(f"Skipping non-first team: {team_name}")
                        continue
                    
                    team_url = link.get_attribute("href")
                    if not team_url or "verein" not in team_url:
                        continue
                    
                    transfermarkt_id = None
                    if "/verein/" in team_url:
                        parts = team_url.split("/verein/")
                        if len(parts) > 1:
                            id_part = parts[1].split("/")[0]
                            if id_part.isdigit():
                                transfermarkt_id = id_part
                    
                    if not transfermarkt_id:
                        continue
                    
                    seen_teams.add(team_name)
                    teams.append({
                        'name': team_name,
                        'transfermarkt_id': transfermarkt_id,
                        'url': team_url
                    })
                    
                    logger.info(f"Found team: {team_name} (ID: {transfermarkt_id})")
                    
                except Exception as e:
                    logger.warning(f"Error parsing team link: {e}")
                    continue
            
            driver.quit()
            
            expected_counts = {
                'GB1': 20,  # Premier League
                'ES1': 20,  # La Liga
                'IT1': 20,  # Serie A
                'L1': 18,   # Bundesliga
                'FR1': 18,  # Ligue 1
                'RU1': 16   # Russian Premier League
            }
            
            expected_count = expected_counts.get(league_id, 20)
            if len(teams) > expected_count:
                teams = sorted(teams, key=lambda x: x['name'])[:expected_count]
                logger.info(f"Filtered to {expected_count} teams for league {league_id}")
            
            logger.info(f"Found {len(teams)} first teams for league {league_id}")
            return teams
            
        except Exception as e:
            logger.error(f"Error scraping league teams: {e}")
            return []

    def scrape_team_squad(self, team_id):
        """Scrape team squad information"""
        try:
            url = f"{self.base_url}/verein/kader/verein/{team_id}"
            
            driver = self.get_driver()
            driver.get(url)
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "items"))
            )
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            driver.quit()
            
            players = []
            player_rows = soup.find_all('tr', class_=['odd', 'even'])
            
            for row in player_rows:
                try:
                    player_data = self._parse_player_row(row)
                    if player_data:
                        players.append(player_data)
                except Exception as e:
                    logger.error(f"Error parsing player row: {e}")
                    continue
            
            return players
            
        except Exception as e:
            logger.error(f"Error scraping team squad: {e}")
            return []
    
    def _parse_player_row(self, row):
        """Parse a player row from the squad table"""
        try:
            number_cell = row.find('div', class_='rn_nummer')
            jersey_number = int(number_cell.get_text(strip=True)) if number_cell and number_cell.get_text(strip=True).isdigit() else None
            
            name_cell = row.find('td', class_='hauptlink')
            if not name_cell:
                return None
                
            player_link = name_cell.find('a')
            if not player_link:
                return None
                
            player_name = player_link.get_text(strip=True)
            player_id = self._extract_player_id(player_link.get('href', ''))
            
            position_cell = row.find_all('td')[1] if len(row.find_all('td')) > 1 else None
            position = position_cell.get_text(strip=True) if position_cell else 'Unknown'
            
            market_value_cell = row.find('td', class_='rechts')
            market_value = self._parse_market_value(market_value_cell.get_text(strip=True)) if market_value_cell else None
            
            return {
                'name': player_name,
                'transfermarkt_id': player_id,
                'position': position,
                'jersey_number': jersey_number,
                'market_value': market_value
            }
            
        except Exception as e:
            logger.error(f"Error parsing player row: {e}")
            return None
    
    def _extract_player_id(self, href):
        """Extract player ID from href"""
        match = re.search(r'/profil/spieler/(\d+)', href)
        return match.group(1) if match else None
    
    def _parse_market_value(self, value_text):
        """Parse market value from text"""
        try:
            if '€' not in value_text:
                return None
                
            value_text = value_text.replace('€', '').replace(' ', '').replace(',', '.')
            
            if 'm' in value_text.lower():
                value = float(value_text.lower().replace('m', '')) * 1000000
            elif 'k' in value_text.lower():
                value = float(value_text.lower().replace('k', '')) * 1000
            else:
                value = float(value_text)
                
            return int(value)
            
        except Exception as e:
            logger.error(f"Error parsing market value: {e}")
            return None
    
    def scrape_player_injuries(self, team_id):
        """Scrape injury information for team players"""
        try:
            url = f"{self.base_url}/verein/verletztenliste/verein/{team_id}"
            
            response = self.session.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            injuries = []
            injury_rows = soup.find_all('tr', class_=['odd', 'even'])
            
            for row in injury_rows:
                try:
                    injury_data = self._parse_injury_row(row)
                    if injury_data:
                        injuries.append(injury_data)
                except Exception as e:
                    logger.error(f"Error parsing injury row: {e}")
                    continue
            
            return injuries
            
        except Exception as e:
            logger.error(f"Error scraping player injuries: {e}")
            return []
    
    def _parse_injury_row(self, row):
        """Parse an injury row from the injuries table"""
        try:
            name_cell = row.find('td', class_='hauptlink')
            if not name_cell:
                return None
                
            player_link = name_cell.find('a')
            if not player_link:
                return None
                
            player_name = player_link.get_text(strip=True)
            player_id = self._extract_player_id(player_link.get('href', ''))
            
            cells = row.find_all('td')
            if len(cells) < 4:
                return None
                
            injury_description = cells[2].get_text(strip=True)
            expected_return = cells[3].get_text(strip=True)
            
            return {
                'player_name': player_name,
                'player_transfermarkt_id': player_id,
                'injury_description': injury_description,
                'expected_return': expected_return,
                'status_type': 'injury'
            }
            
        except Exception as e:
            logger.error(f"Error parsing injury row: {e}")
            return None
