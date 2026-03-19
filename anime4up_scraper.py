import requests
from bs4 import BeautifulSoup
import re
import urllib3
from urllib.parse import urlencode

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Anime4upScraper:
    def __init__(self):
        self.base_url = "https://w1.anime4up.rest"
        # Using the user's provided ScraperAPI key
        self.api_key = "70b7ccc8c48d7bf60ee80ab2ee12ff09" 
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

    def _get_with_scraperapi(self, url, render=False):
        """Helper to call ScraperAPI."""
        params = {'api_key': self.api_key, 'url': url}
        if render:
            params['render'] = 'true'
            params['premium'] = 'true'
        
        api_url = f"http://api.scraperapi.com?{urlencode(params)}"
        try:
            return requests.get(api_url, timeout=110)
        except Exception as e:
            print(f"ScraperAPI Error: {e}")
            return None

    def get_latest_episodes(self):
        """Scrapes the latest episodes from Anime4up."""
        url = f"{self.base_url}/episode/"
        response = self._get_with_scraperapi(url, render=False)
        if not response or response.status_code != 200: return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        episodes = []
        
        # Anime4up structure for episodes
        for div in soup.find_all('div', class_='episodes-card-container'):
            a_tag = div.find('a', href=True)
            title_tag = div.find('h3')
            if a_tag and title_tag:
                title = title_tag.text.strip()
                ep_url = a_tag['href']
                episodes.append({
                    'title': title,
                    'url': ep_url
                })
        
        # Fallback if class names are different
        if not episodes:
            for a in soup.find_all('a', href=True):
                if '/episode/' in a['href'] and a.find('h3'):
                    episodes.append({
                        'title': a.find('h3').text.strip(),
                        'url': a['href']
                    })
                    
        return episodes

    def get_anime_details(self, anime_url):
        """Scrapes details for a specific anime."""
        response = self._get_with_scraperapi(anime_url, render=False)
        if not response or response.status_code != 200: return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        details = {}
        
        title_tag = soup.find('h1')
        details['title'] = title_tag.text.strip() if title_tag else "Unknown"
        
        genres = []
        for a in soup.find_all('a', href=True):
            if '/anime-genre/' in a['href']:
                genres.append(a.text.strip())
        details['genres'] = list(set(genres))
        
        # Info extraction
        for li in soup.find_all('li'):
            text = li.text.strip()
            if ':' in text:
                parts = text.split(':', 1)
                k = parts[0].strip()
                v = parts[1].strip()
                if 'بداية العرض' in k: details['year'] = v
                elif 'حالة الأنمي' in k: details['status'] = v
                elif 'نوع الأنمي' in k: details['type'] = v
                elif 'الموسم' in k: details['season'] = v
        
        desc_tag = soup.find('div', class_='anime-story') or soup.find('p', class_='anime-story')
        details['description'] = desc_tag.text.strip() if desc_tag else ""
        
        mal_link = soup.find('a', href=re.compile(r'myanimelist\.net/anime/'))
        if mal_link:
            details['mal_url'] = mal_link['href']
            
        return details

    def get_episode_data(self, episode_url):
        """Scrapes video servers and download links."""
        response = self._get_with_scraperapi(episode_url, render=True)
        if not response or response.status_code != 200: return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        data = {
            'watch_servers': [],
            'download_links': []
        }
        
        # Watch servers are usually in a list or buttons
        for li in soup.find_all('li'):
            if 'server' in li.get('class', []) or 'watch' in li.text.lower():
                data['watch_servers'].append(li.text.strip())
        
        # Download links are in a table or list
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.text.strip().lower()
            if any(d in href.lower() for d in ['mega.nz', 'mediafire', 'gofile', 'workupload', 'mp4upload']):
                # Try to find quality in the same row or parent
                quality = "Unknown"
                parent = a.find_parent()
                parent_text = parent.text if parent else ""
                if '1080' in parent_text or 'fhd' in parent_text: quality = "1080p"
                elif '720' in parent_text or 'hd' in parent_text: quality = "720p"
                elif '480' in parent_text or 'sd' in parent_text: quality = "480p"
                
                data['download_links'].append({
                    'quality': quality,
                    'host': text if len(text) < 20 else "Download",
                    'url': href
                })
                
        return data
