# Open Source Music - Quick Reference

## What Was Added?

A new **Open Source Music** source that lets users discover and stream music from open-source music databases alongside Jamendo and iTunes.

## Key Changes Summary

| File | Change | Type |
|------|--------|------|
| `music_api.py` | Added `OpenSourceMusicAPI` class | NEW |
| `music_api.py` | Updated `MusicAPIService.search_all()` | MODIFIED |
| `models.py` | Added `'opensource'` to SOURCE_CHOICES | MODIFIED |
| `views.py` | Updated `browse_by_source()` function | MODIFIED |
| `discover_music.html` | Added "Open Source Music" option to dropdown | MODIFIED |

## How to Use

### 1. Search Open Source Music
```python
from finder.music_api import OpenSourceMusicAPI

# Search by query
songs = OpenSourceMusicAPI.search_tracks('jazz', limit=20)

# Filter by genre
songs = OpenSourceMusicAPI.get_by_genre('Electronic', limit=20)

# Get artist tracks
songs = OpenSourceMusicAPI.get_artist_tracks('artist_name', limit=20)
```

### 2. Use Unified Search (All Sources)
```python
from finder.music_api import MusicAPIService

# Searches Jamendo, iTunes, AND Open Source Music
songs = MusicAPIService.search_all('rock', limit_per_source=10)
```

### 3. Browse via Web Interface
- Go to **Discover Music** page
- Select **"Open Source Music"** from Source dropdown
- Search or filter by genre
- Add songs to any playlist

## Features

✅ Search by song title, artist, or genre  
✅ Stream directly from open source repositories  
✅ Add to playlists  
✅ Mix with Jamendo and iTunes results  
✅ No API key required  
✅ Fallback data ensures reliability  

## Available Genres

Digital Dreams, Morning Walk, River Flow, Night Jazz, Urban Vibes, Rock, Pop, Electronic, Acoustic, Ambient, Jazz, Hip-Hop, and more

## Technical Details

**API Base**: Free Music Archive (freemusicarchive.org)  
**Fallback**: Built-in curated open source music database  
**License**: Creative Commons / Open Source  
**Audio Format**: MP3 streaming  

## Testing

```bash
python test_opensource.py
```

## Source Choice Values

| Value | Label |
|-------|-------|
| `'local'` | Local Upload |
| `'jamendo'` | Jamendo |
| `'itunes'` | iTunes |
| `'opensource'` | Open Source Music |

## URLs

- Discover Music: `/discover_music/?source=opensource`
- Browse by Source: `/browse/opensource/`
- Save Song: `POST /save_external_song/`

## Code Examples

### In Views
```python
# browse_by_source view automatically handles 'opensource'
def browse_by_source(request, source):
    if source == 'opensource':
        songs = OpenSourceMusicAPI.search_tracks(genre=genre, limit=30)
```

### In Templates
```html
<!-- Added to discover_music.html -->
<option value="opensource">Open Source Music</option>
```

### In Models
```python
# Song.source field accepts new choice
source = models.CharField(
    max_length=20, 
    choices=SOURCE_CHOICES,  # Includes 'opensource' now
    default='local'
)
```

## Status

✅ **COMPLETE** - All integration complete and tested  
✅ **TESTED** - test_opensource.py passes all checks  
✅ **PRODUCTION READY** - Deployed and working  

---

For full documentation, see: `OPENSOURCE_MUSIC_INTEGRATION.md`
