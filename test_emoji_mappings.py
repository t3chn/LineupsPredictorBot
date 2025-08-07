#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fetchers.logo_scraper import LogoScraper

def test_emoji_mappings():
    """Test emoji mappings for various teams"""
    scraper = LogoScraper()
    
    test_teams = [
        'Liverpool', 'Real Madrid', 'Bayern Munich', 'Juventus', 'PSG', 
        'Spartak Moscow', 'Zenit', 'AC Milan', 'Chelsea', 'Unknown Team'
    ]
    
    print('Testing emoji mappings:')
    for team in test_teams:
        emoji = scraper.get_fallback_emoji(team)
        print(f'{team}: {emoji}')

if __name__ == "__main__":
    test_emoji_mappings()
