import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('Telegram_Token')
DATABASE_URL = os.getenv('DATABASE_URL')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

LEAGUES = {
    'EPL': {
        'name': 'Premier League',
        'emoji': '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
        'transfermarkt_id': 'GB1',
        'season': '2025'
    },
    'La Liga': {
        'name': 'La Liga',
        'emoji': '🇪🇸',
        'transfermarkt_id': 'ES1',
        'season': '2025'
    },
    'Serie A': {
        'name': 'Serie A',
        'emoji': '🇮🇹',
        'transfermarkt_id': 'IT1',
        'season': '2025'
    },
    'Bundesliga': {
        'name': 'Bundesliga',
        'emoji': '🇩🇪',
        'transfermarkt_id': 'L1',
        'season': '2025'
    },
    'Ligue 1': {
        'name': 'Ligue 1',
        'emoji': '🇫🇷',
        'transfermarkt_id': 'FR1',
        'season': '2025'
    },
    'RPL': {
        'name': 'Russian Premier League',
        'emoji': '🇷🇺',
        'transfermarkt_id': 'RU1',
        'season': '2025'
    }
}

TRUSTED_JOURNALISTS = [
    'FabrizioRomano',
    'David_Ornstein',
    'JamesOlley',
    'SamiMokbel81',
    'JPercyTelegraph',
    'SkySports_Keith',
    'ChrisWheatley_',
    'GuillemBalague',
    'MatteMoretto',
    'DiMarzio',
    'AlfredoPedulla',
    'SkySportsPL'
]

UPDATE_INTERVAL_HOURS = 10
