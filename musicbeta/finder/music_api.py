"""
Music API Integration Service
Fetches songs dynamically from free music APIs
"""
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
try:
    import requests
except ModuleNotFoundError:
    requests = None
from typing import List, Dict, Optional


def _get_json(url: str, params: Optional[Dict] = None, timeout: int = 6):
    """Fetch JSON using requests when available, otherwise urllib."""
    if requests is not None:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json(), response.status_code

    full_url = url
    if params:
        query = urlencode(params)
        separator = '&' if '?' in url else '?'
        full_url = f"{url}{separator}{query}"

    request = Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(request, timeout=timeout) as response:
        status_code = response.getcode()
        body = response.read().decode('utf-8')
        return json.loads(body), status_code


class OpenSourceMusicAPI:
    """Open Source Music Database - Free Music Archive"""
    FMA_API_BASE = "https://freemusicarchive.org/api/get"
    
    # Fallback open source music sources
    FALLBACK_SOURCES = [
        {
            'id': 'opensource_1',
            'title': 'Digital Dreams',
            'artist': 'Blue Moon Records',
            'genre': 'Electronic',
            'audio_url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
            'cover_image': '',
            'duration': 300,
            'source': 'opensource',
            'external_id': '1'
        },
        {
            'id': 'opensource_2',
            'title': 'Morning Walk',
            'artist': 'Open Source Collective',
            'genre': 'Acoustic',
            'audio_url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3',
            'cover_image': '',
            'duration': 240,
            'source': 'opensource',
            'external_id': '2'
        },
        {
            'id': 'opensource_3',
            'title': 'River Flow',
            'artist': 'Free Sound Initiative',
            'genre': 'Ambient',
            'audio_url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3',
            'cover_image': '',
            'duration': 180,
            'source': 'opensource',
            'external_id': '3'
        },
        {
            'id': 'opensource_4',
            'title': 'Night Jazz',
            'artist': 'Creative Commons Band',
            'genre': 'Jazz',
            'audio_url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3',
            'cover_image': '',
            'duration': 270,
            'source': 'opensource',
            'external_id': '4'
        },
        {
            'id': 'opensource_5',
            'title': 'Urban Vibes',
            'artist': 'OpenBeats',
            'genre': 'Hip-Hop',
            'audio_url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3',
            'cover_image': '',
            'duration': 210,
            'source': 'opensource',
            'external_id': '5'
        },
        {
            'id': 'opensource_6',
            'title': 'Sunrise Drive',
            'artist': 'Creative Loop',
            'genre': 'Indie',
            'audio_url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-6.mp3',
            'cover_image': '',
            'duration': 260,
            'source': 'opensource',
            'external_id': '6'
        },
        {
            'id': 'opensource_7',
            'title': 'Late Night Code',
            'artist': 'Open Wave',
            'genre': 'Lo-Fi',
            'audio_url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-7.mp3',
            'cover_image': '',
            'duration': 230,
            'source': 'opensource',
            'external_id': '7'
        },
        {
            'id': 'opensource_8',
            'title': 'City Lights',
            'artist': 'Free Horizon',
            'genre': 'Pop',
            'audio_url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3',
            'cover_image': '',
            'duration': 245,
            'source': 'opensource',
            'external_id': '8'
        },
        {
            'id': 'opensource_9',
            'title': 'Deep Focus',
            'artist': 'Open Beats Lab',
            'genre': 'Ambient',
            'audio_url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3',
            'cover_image': '',
            'duration': 315,
            'source': 'opensource',
            'external_id': '9'
        },
        {
            'id': 'opensource_10',
            'title': 'Golden Hour',
            'artist': 'Commons Club',
            'genre': 'Acoustic',
            'audio_url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-10.mp3',
            'cover_image': '',
            'duration': 280,
            'source': 'opensource',
            'external_id': '10'
        },
    ]
    
    @staticmethod
    def search_tracks(query: str = "", limit: int = 20, genre: str = "") -> List[Dict]:
        """
        Search for open source music tracks
        
        Args:
            query: Search term for song/artist name
            limit: Number of results to return
            genre: Genre filter
            
        Returns:
            List of song dictionaries
        """
        try:
            songs = OpenSourceMusicAPI.FALLBACK_SOURCES.copy()
            
            # Try FMA API first
            if query:
                try:
                    params = {
                        'method': 'Track.search',
                        'search_query': query,
                        'limit': min(limit, 50),
                        'api_key': ''
                    }
                    
                    data, status_code = _get_json(
                        OpenSourceMusicAPI.FMA_API_BASE,
                        params=params,
                        timeout=5
                    )
                    
                    if status_code == 200:
                        
                        if data.get('status') == 'ok' and data.get('dataset'):
                            api_songs = []
                            for track in data.get('dataset', []):
                                if track.get('track_file_url'):
                                    api_songs.append({
                                        'id': f"opensource_{track.get('track_id')}",
                                        'title': track.get('track_title', 'Unknown'),
                                        'artist': track.get('artist_name', 'Unknown'),
                                        'genre': track.get('genre_title', 'Open Source'),
                                        'audio_url': track.get('track_file_url', ''),
                                        'cover_image': track.get('track_image_file', '') or '',
                                        'duration': int(track.get('track_duration', 180)),
                                        'source': 'opensource',
                                        'external_id': track.get('track_id')
                                    })
                            
                            if api_songs:
                                return api_songs[:limit]
                except Exception:
                    pass  # Fall back to local list
            
            # Filter by genre if specified
            if genre:
                songs = [s for s in songs if genre.lower() in s['genre'].lower()]
            
            # Filter by query if specified
            if query:
                query_lower = query.lower()
                songs = [s for s in songs if 
                        query_lower in s['title'].lower() or 
                        query_lower in s['artist'].lower() or
                        query_lower in s['genre'].lower()]
            
            return songs[:limit]
            
        except Exception as e:
            print(f"Error in OpenSourceMusicAPI: {e}")
            return []
    
    @staticmethod
    def get_by_genre(genre: str, limit: int = 20) -> List[Dict]:
        """Get tracks by genre"""
        songs = OpenSourceMusicAPI.search_tracks(query="", genre=genre, limit=limit)
        return songs
    
    @staticmethod
    def get_artist_tracks(artist: str, limit: int = 20) -> List[Dict]:
        """Get all tracks from a specific artist"""
        songs = OpenSourceMusicAPI.search_tracks(query=artist, limit=limit)
        return songs


class JamendoAPI:
    """Jamendo API - Free Creative Commons Music"""
    BASE_URL = "https://api.jamendo.com/v3.0"
    CLIENT_ID = "56d30c95"  # Public client ID for testing
    
    @staticmethod
    def search_tracks(query: str = "", limit: int = 20, genre: str = "") -> List[Dict]:
        """
        Search for tracks on Jamendo
        
        Args:
            query: Search term for song/artist name
            limit: Number of results to return
            genre: Genre filter (rock, pop, jazz, electronic, etc.)
            
        Returns:
            List of song dictionaries
        """
        try:
            params = {
                'client_id': JamendoAPI.CLIENT_ID,
                'format': 'json',
                'limit': limit,
                'include': 'musicinfo',
                'audioformat': 'mp32'
            }
            
            if query:
                params['namesearch'] = query
            
            if genre:
                params['tags'] = genre
            
            data, _ = _get_json(
                f"{JamendoAPI.BASE_URL}/tracks/",
                params=params,
                timeout=6
            )
            
            # Transform to our format
            songs = []
            for track in data.get('results', []):
                songs.append({
                    'id': f"jamendo_{track['id']}",
                    'title': track['name'],
                    'artist': track['artist_name'],
                    'genre': track.get('musicinfo', {}).get('tags', {}).get('genres', ['Unknown'])[0] if track.get('musicinfo', {}).get('tags', {}).get('genres') else 'Unknown',
                    'audio_url': track.get('audio', ''),
                    'cover_image': track.get('image', ''),
                    'duration': track.get('duration', 0),
                    'source': 'jamendo',
                    'external_id': track['id']
                })
            
            return songs
            
        except Exception as e:
            print(f"Error fetching from Jamendo: {e}")
            return []
    
    @staticmethod
    def get_popular_tracks(limit: int = 20) -> List[Dict]:
        """Get popular tracks from Jamendo"""
        try:
            params = {
                'client_id': JamendoAPI.CLIENT_ID,
                'format': 'json',
                'limit': limit,
                'order': 'popularity_week',
                'include': 'musicinfo',
                'audioformat': 'mp32'
            }
            
            data, _ = _get_json(
                f"{JamendoAPI.BASE_URL}/tracks/",
                params=params,
                timeout=6
            )
            
            songs = []
            for track in data.get('results', []):
                songs.append({
                    'id': f"jamendo_{track['id']}",
                    'title': track['name'],
                    'artist': track['artist_name'],
                    'genre': track.get('musicinfo', {}).get('tags', {}).get('genres', ['Unknown'])[0] if track.get('musicinfo', {}).get('tags', {}).get('genres') else 'Unknown',
                    'audio_url': track.get('audio', ''),
                    'cover_image': track.get('image', ''),
                    'duration': track.get('duration', 0),
                    'source': 'jamendo',
                    'external_id': track['id']
                })
            
            return songs
            
        except Exception as e:
            print(f"Error fetching popular tracks: {e}")
            return []


class iTunesAPI:
    """iTunes Search API - Music Previews"""
    BASE_URL = "https://itunes.apple.com/search"
    
    @staticmethod
    def search_tracks(query: str, limit: int = 20) -> List[Dict]:
        """
        Search for tracks on iTunes
        
        Args:
            query: Search term for song/artist/album
            limit: Number of results to return
            
        Returns:
            List of song dictionaries with 30-second previews
        """
        try:
            params = {
                'term': query,
                'media': 'music',
                'entity': 'song',
                'limit': limit
            }
            
            data, _ = _get_json(
                iTunesAPI.BASE_URL,
                params=params,
                timeout=6
            )
            
            songs = []
            for track in data.get('results', []):
                if track.get('previewUrl'):  # Only include tracks with previews
                    songs.append({
                        'id': f"itunes_{track['trackId']}",
                        'title': track.get('trackName', 'Unknown'),
                        'artist': track.get('artistName', 'Unknown'),
                        'genre': track.get('primaryGenreName', 'Unknown'),
                        'audio_url': track.get('previewUrl', ''),
                        'cover_image': track.get('artworkUrl100', '').replace('100x100', '600x600'),
                        'duration': int(track.get('trackTimeMillis', 30000) / 1000),
                        'source': 'itunes',
                        'external_id': track['trackId']
                    })
            
            return songs
            
        except Exception as e:
            print(f"Error fetching from iTunes: {e}")
            return []


class MusicAPIService:
    """Unified music API service combining multiple sources"""
    
    @staticmethod
    def search_all(query: str = "", limit_per_source: int = 10, genre: str = "") -> List[Dict]:
        """
        Search across all available music APIs
        
        Args:
            query: Search term
            limit_per_source: Results per API
            genre: Genre filter
            
        Returns:
            Combined list of songs from all sources
        """
        all_songs = []
        
        # Fetch from Open Source (Free Music Archive)
        opensource_songs = OpenSourceMusicAPI.search_tracks(query, limit_per_source, genre)
        all_songs.extend(opensource_songs)
        
        # Fetch from Jamendo
        jamendo_songs = JamendoAPI.search_tracks(query, limit_per_source, genre)
        all_songs.extend(jamendo_songs)
        
        # Fetch from iTunes (if query provided)
        if query:
            itunes_songs = iTunesAPI.search_tracks(query, limit_per_source)
            all_songs.extend(itunes_songs)
        
        return all_songs
    
    @staticmethod
    def get_trending(limit: int = 20) -> List[Dict]:
        """Get trending/popular songs from all sources"""
        all_songs = []
        
        # Get from open source
        opensource_songs = OpenSourceMusicAPI.search_tracks("", limit // 3)
        all_songs.extend(opensource_songs)
        
        # Get from Jamendo
        jamendo_songs = JamendoAPI.get_popular_tracks(limit // 3)
        all_songs.extend(jamendo_songs)
        
        return all_songs[:limit]
