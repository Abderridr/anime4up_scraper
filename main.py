from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
import re
import os
import urllib3
from urllib.parse import urlencode, unquote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

class Anime4upScraper:
    def __init__(self):
        self.base_url = "https://w1.anime4up.rest"
        self.api_key = "70b7ccc8c48d7bf60ee80ab2ee12ff09" 
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

    def _get_with_scraperapi(self, url, render=False):
        params = {'api_key': self.api_key, 'url': url}
        if render:
            params['render'] = 'true'
            params['premium'] = 'true'
        api_url = f"http://api.scraperapi.com?{urlencode(params)}"
        try:
            return requests.get(api_url, timeout=110)
        except Exception as e:
            return None

    def get_latest_episodes(self):
        url = f"{self.base_url}/episode/"
        response = self._get_with_scraperapi(url, render=False)
        if not response or response.status_code != 200: return []
        soup = BeautifulSoup(response.text, 'html.parser')
        episodes = []
        
        # More robust search for episode cards
        for card in soup.find_all(['div', 'article']):
            ep_link = card.find('a', href=re.compile(r'/episode/'))
            anime_link = card.find('a', href=re.compile(r'/anime/'))
            
            if ep_link and anime_link:
                ep_title = ep_link.text.strip()
                anime_title = anime_link.text.strip()
                ep_url = ep_link['href']
                full_title = f"{anime_title} {ep_title}"
                episodes.append({'title': full_title, 'url': ep_url})
        
        if not episodes:
            for a in soup.find_all('a', href=re.compile(r'/episode/')):
                title = a.text.strip()
                if title and "الحلقة" in title:
                    episodes.append({'title': title, 'url': a['href']})
                    
        return episodes

    def get_anime_details(self, anime_url):
        response = self._get_with_scraperapi(anime_url, render=False)
        if not response or response.status_code != 200: return None
        soup = BeautifulSoup(response.text, 'html.parser')
        details = {'title': soup.find('h1').text.strip() if soup.find('h1') else "Unknown", 'genres': list(set([a.text.strip() for a in soup.find_all('a', href=True) if '/anime-genre/' in a['href']]))}
        for li in soup.find_all('li'):
            txt = li.text.strip()
            if ':' in txt:
                k, v = txt.split(':', 1)
                if 'بداية العرض' in k: details['year'] = v.strip()
                elif 'حالة الأنمي' in k: details['status'] = v.strip()
        return details

    def get_episode_data(self, episode_url):
        response = self._get_with_scraperapi(episode_url, render=True)
        if not response or response.status_code != 200: return None
        soup = BeautifulSoup(response.text, 'html.parser')
        data = {'watch_servers': [], 'download_links': []}
        
        # Improved table parsing for Anime4up
        table = soup.find('table')
        if table:
            rows = table.find_all('tr')
            for row in rows[1:]: # Skip header
                cols = row.find_all('td')
                if len(cols) >= 3:
                    link_tag = cols[0].find('a', href=True)
                    server_name = cols[1].text.strip()
                    quality = cols[2].text.strip()
                    
                    if link_tag:
                        href = link_tag['href']
                        data['download_links'].append({
                            'quality': quality,
                            'host': server_name,
                            'url': href
                        })
                        if server_name not in data['watch_servers']:
                            data['watch_servers'].append(server_name)
        
        # Fallback for download links if table parsing fails
        if not data['download_links']:
            for a in soup.find_all('a', href=True):
                href = a['href']
                if any(d in href.lower() for d in ['mega.nz', 'mediafire', 'gofile', 'workupload', 'mp4upload']):
                    q = "Unknown"
                    pt = a.find_parent().text.lower() if a.find_parent() else ""
                    if '1080' in pt or 'fhd' in pt: q = "1080p"
                    elif '720' in pt or 'hd' in pt: q = "720p"
                    elif '480' in pt or 'sd' in pt: q = "480p"
                    data['download_links'].append({'quality': q, 'host': a.text.strip()[:20], 'url': href})
                    
        return data

scraper = Anime4upScraper()

@app.route('/')
def index():
    return jsonify({'message': 'Anime4up API Live! 🚀', 'endpoints': ['/anime/anime4up/recent-episodes', '/anime/anime4up/info?id={id}', '/anime/anime4up/watch?episodeId={episodeId}']})

@app.route('/anime/anime4up/recent-episodes')
def recent_episodes():
    latest = scraper.get_latest_episodes()
    results = []
    for ep in latest:
        match = re.search(r'(.*?)\s+(الحلقة|الأوفا)\s+(\d+)', ep['title'])
        if match:
            title = match.group(1).strip()
            num = match.group(3)
        else:
            title = ep['title']
            num = "1"
            
        results.append({
            'id': re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-'), 
            'title': title, 
            'episodeId': ep['url'].strip('/').split('/')[-1], 
            'episodeNumber': int(num) if num.isdigit() else 1, 
            'url': ep['url']
        })
    return jsonify({'results': results, 'count': len(results)})

@app.route('/anime/anime4up/info')
def anime_info():
    anime_id = request.args.get('id')
    details = scraper.get_anime_details(f"https://w1.anime4up.rest/anime/{anime_id}/")
    return jsonify(details) if details else (jsonify({'error': 'Not found'}), 404)

@app.route('/anime/anime4up/watch')
def watch_episode():
    episode_id = unquote(request.args.get('episodeId', ''))
    # Ensure the episode_id is correctly formatted for the URL
    # If it doesn't start with the anime name, it might be a partial ID
    episode_url = f"https://w1.anime4up.rest/episode/{episode_id}/"
    
    data = scraper.get_episode_data(episode_url)
    if not data: 
        return jsonify({
            'error': 'Not found',
            'attempted_url': episode_url,
            'episode_id': episode_id
        }), 404
        
    return jsonify({
        'headers': {'Referer': 'https://w1.anime4up.rest/'}, 
        'sources': [{'url': l['url'], 'quality': l['quality'], 'host': l['host']} for l in data['download_links']], 
        'watch_servers': data['watch_servers']
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3000)))
