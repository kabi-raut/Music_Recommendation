"""Jamendo API integration for dynamic music discovery."""
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
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


class JamendoAPI:
    """Jamendo API - Free Creative Commons Music"""
    BASE_URL = "https://api.jamendo.com/v3.0"
    CLIENT_ID = "56d30c95"  # Public client ID for testing

    @staticmethod
    def _get_client_id() -> str:
        try:
            configured = (getattr(settings, 'JAMENDO_CLIENT_ID', '') or '').strip()
        except ImproperlyConfigured:
            configured = (os.environ.get('JAMENDO_CLIENT_ID', '') or '').strip()
        return configured or JamendoAPI.CLIENT_ID

    @staticmethod
    def _extract_error_message(data: Dict) -> str:
        headers = data.get('headers') or {}
        if isinstance(headers, dict) and headers.get('status') == 'failed':
            return headers.get('error_message') or 'Jamendo API request failed.'
        return ''
    
    @staticmethod
    def search_tracks(query: str = "", limit: int = 20, genre: str = "", raise_on_error: bool = False) -> List[Dict]:
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
                'client_id': JamendoAPI._get_client_id(),
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

            error_message = JamendoAPI._extract_error_message(data)
            if error_message:
                raise RuntimeError(error_message)
            
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
            if raise_on_error:
                raise
            print(f"Error fetching from Jamendo: {e}")
            return []
    
    @staticmethod
    def get_popular_tracks(limit: int = 20) -> List[Dict]:
        """Get popular tracks from Jamendo"""
        try:
            params = {
                'client_id': JamendoAPI._get_client_id(),
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

            error_message = JamendoAPI._extract_error_message(data)
            if error_message:
                raise RuntimeError(error_message)
            
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


class OpenSourceMusicAPI:
    """Open Source Music API - Free Music Archive and curated open source music"""
    
    # Fallback data for open source music (Creative Commons licensed)
    FALLBACK_DATA = [
        # Electronic
        {'title': 'Digital Dreams', 'artist': 'Synthet', 'genre': 'Electronic', 'duration': 240},
        {'title': 'Neon Nights', 'artist': 'ElectroBeat', 'genre': 'Electronic', 'duration': 210},
        {'title': 'Cyber Space', 'artist': 'FutureSounds', 'genre': 'Electronic', 'duration': 195},
        # Jazz
        {'title': 'Blue Moon Jazz', 'artist': 'Jazz Quartet', 'genre': 'Jazz', 'duration': 300},
        {'title': 'Smooth Sailing', 'artist': 'Cool Jazz', 'genre': 'Jazz', 'duration': 240},
        {'title': 'Midnight Session', 'artist': 'Jazz Fusion', 'genre': 'Jazz', 'duration': 280},
        # Acoustic
        {'title': 'Guitar Bliss', 'artist': 'Acoustic Masters', 'genre': 'Acoustic', 'duration': 220},
        {'title': 'Unplugged', 'artist': 'Folk Singer', 'genre': 'Acoustic', 'duration': 200},
        {'title': 'Strings & Soul', 'artist': 'Classical Crossover', 'genre': 'Acoustic', 'duration': 260},
        # Rock
        {'title': 'Rock Anthem', 'artist': 'Stone Hearts', 'genre': 'Rock', 'duration': 250},
        {'title': 'Electric Roads', 'artist': 'Rock Legends', 'genre': 'Rock', 'duration': 230},
        # Pop
        {'title': 'Pop Sensation', 'artist': 'Pop Stars', 'genre': 'Pop', 'duration': 210},
        {'title': 'Catchy Tune', 'artist': 'Pop Charts', 'genre': 'Pop', 'duration': 200},
        # Ambient
        {'title': 'Peaceful Mind', 'artist': 'Ambient Soundscapes', 'genre': 'Ambient', 'duration': 300},
        {'title': 'Zen Master', 'artist': 'Meditation Music', 'genre': 'Ambient', 'duration': 280},
        # Hip-Hop
        {'title': 'Urban Beats', 'artist': 'Hip Hop Kings', 'genre': 'Hip-Hop', 'duration': 220},
        {'title': 'Rhyme Time', 'artist': 'Rap Masters', 'genre': 'Hip-Hop', 'duration': 240},
    ]

    @staticmethod
    def search_tracks(query: str = "", limit: int = 20, genre: str = "") -> List[Dict]:
        """
        Search for open source tracks by query and/or genre
        
        Args:
            query: Search term for song/artist name
            limit: Number of results to return
            genre: Optional genre filter
            
        Returns:
            List of song dictionaries
        """
        try:
            results = []
            query_lower = query.lower() if query else ""
            genre_lower = genre.lower() if genre else ""

            for track in OpenSourceMusicAPI.FALLBACK_DATA:
                # Filter by query if provided
                if query_lower:
                    if not (query_lower in track['title'].lower() or query_lower in track['artist'].lower()):
                        continue
                
                # Filter by genre if provided
                if genre_lower:
                    if genre_lower not in track['genre'].lower():
                        continue
                
                results.append({
                    'id': f"opensource_{len(results)}",
                    'title': track['title'],
                    'artist': track['artist'],
                    'genre': track['genre'],
                    'audio_url': '',  # Would be set from actual FMA API
                    'cover_image': '',  # Would be set from actual FMA API
                    'duration': track['duration'],
                    'source': 'opensource',
                    'external_id': f"fma_{len(results)}"
                })
                
                if len(results) >= limit:
                    break
            
            return results
            
        except Exception as e:
            print(f"Error searching open source music: {e}")
            return []

    @staticmethod
    def get_by_genre(genre: str, limit: int = 20) -> List[Dict]:
        """
        Get open source tracks by genre
        
        Args:
            genre: Genre to filter by
            limit: Number of results to return
            
        Returns:
            List of song dictionaries
        """
        return OpenSourceMusicAPI.search_tracks(query="", genre=genre, limit=limit)

    @staticmethod
    def get_artist_tracks(artist: str, limit: int = 20) -> List[Dict]:
        """
        Get tracks from a specific artist
        
        Args:
            artist: Artist name to search for
            limit: Number of results to return
            
        Returns:
            List of song dictionaries
        """
        return OpenSourceMusicAPI.search_tracks(query=artist, limit=limit)


class MusicAPIService:
    """Music service using iTunes for search and trending."""
    
    @staticmethod
    def search_all(query: str = "", limit_per_source: int = 16, genre: str = "") -> List[Dict]:
        """Search using iTunes only."""
        return iTunesAPI.search_tracks(query=query, limit=limit_per_source, genre=genre)
    
    @staticmethod
    def get_trending(limit: int = 20) -> List[Dict]:
        """Get trending tracks from iTunes only."""
        return iTunesAPI.get_popular_tracks(limit=limit)


class iTunesAPI:
    """iTunes API integration - Free music search service"""
    BASE_URL = "https://itunes.apple.com/search"

    @staticmethod
    def search_tracks(query: str = "", limit: int = 20, genre: str = "", raise_on_error: bool = False) -> List[Dict]:
        """
        Search for tracks on iTunes
        
        Args:
            query: Search term for song/artist name
            limit: Number of results to return
            genre: Genre filter (optional)
            
        Returns:
            List of song dictionaries
        """
        try:
            if not query and not genre:
                return iTunesAPI._get_popular_tracks(limit)
            
            search_term = query or genre
            params = {
                'term': search_term,
                'media': 'music',
                'entity': 'song',
                'limit': min(limit * 2, 200),  # Get more to filter
            }
            
            data, _ = _get_json(iTunesAPI.BASE_URL, params=params, timeout=6)
            results = data.get('results', [])
            
            songs = []
            for track in results:
                # Filter out explicit or non-relevant results
                if track.get('kind') != 'song':
                    continue
                
                # If genre filter specified, check it
                if genre and genre.lower() not in track.get('primaryGenreName', '').lower():
                    continue
                
                song_data = {
                    'id': f"itunes_{track.get('trackId')}",
                    'title': track.get('trackName', 'Unknown Title'),
                    'artist': track.get('artistName', 'Unknown Artist'),
                    'genre': track.get('primaryGenreName', 'Unknown'),
                    'audio_url': track.get('previewUrl', ''),
                    'cover_image': track.get('artworkUrl100', ''),
                    'duration': int((track.get('trackTimeMillis', 0) or 0) / 1000),
                    'source': 'itunes',
                    'external_id': str(track.get('trackId', ''))
                }
                
                if song_data['audio_url']:  # Only include if preview URL available
                    songs.append(song_data)
                    if len(songs) >= limit:
                        break
            
            return songs
            
        except Exception as e:
            if raise_on_error:
                raise
            print(f"Error fetching from iTunes: {e}")
            return []
    
    @staticmethod
    def _get_popular_tracks(limit: int) -> List[Dict]:
        """Get popular tracks by searching common genres"""
        try:
            popular_searches = ['pop', 'rock', 'hip hop', 'electronic', 'jazz']
            all_songs = []
            
            for search_term in popular_searches:
                if len(all_songs) >= limit:
                    break
                    
                params = {
                    'term': search_term,
                    'media': 'music',
                    'entity': 'song',
                    'limit': 20,
                }
                
                data, _ = _get_json(iTunesAPI.BASE_URL, params=params, timeout=6)
                results = data.get('results', [])
                
                for track in results:
                    if track.get('kind') != 'song' or not track.get('previewUrl'):
                        continue
                    
                    all_songs.append({
                        'id': f"itunes_{track.get('trackId')}",
                        'title': track.get('trackName', 'Unknown Title'),
                        'artist': track.get('artistName', 'Unknown Artist'),
                        'genre': track.get('primaryGenreName', 'Unknown'),
                        'audio_url': track.get('previewUrl', ''),
                        'cover_image': track.get('artworkUrl100', ''),
                        'duration': int((track.get('trackTimeMillis', 0) or 0) / 1000),
                        'source': 'itunes',
                        'external_id': str(track.get('trackId', ''))
                    })
                    
                    if len(all_songs) >= limit:
                        break
            
            return all_songs[:limit]
        except Exception as e:
            print(f"Error fetching popular iTunes tracks: {e}")
            return []
    
    @staticmethod
    def get_popular_tracks(limit: int = 20) -> List[Dict]:
        """Get popular tracks from iTunes"""
        return iTunesAPI._get_popular_tracks(limit)
