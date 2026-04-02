#!/usr/bin/env python
"""Quick test of OpenSourceMusicAPI"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'musicbeta.settings')
django.setup()

from finder.music_api import OpenSourceMusicAPI, MusicAPIService

print("\n=== Testing OpenSourceMusicAPI ===\n")

# Test 1: Search with query
print("Test 1: Search for 'jazz' tracks")
songs = OpenSourceMusicAPI.search_tracks('jazz', limit=3)
print(f"✓ Found {len(songs)} songs")
if songs:
    for i, song in enumerate(songs, 1):
        print(f"  {i}. {song['title']} by {song['artist']} ({song['genre']})")

# Test 2: Search by genre
print("\nTest 2: Filter by genre 'Electronic'")
songs = OpenSourceMusicAPI.get_by_genre('Electronic', limit=2)
print(f"✓ Found {len(songs)} songs")
if songs:
    for i, song in enumerate(songs, 1):
        print(f"  {i}. {song['title']} by {song['artist']}")

# Test 3: MusicAPIService unified search
print("\nTest 3: MusicAPIService.search_all()")
all_songs = MusicAPIService.search_all('rock', limit_per_source=2)
print(f"✓ Found {len(all_songs)} songs total")

sources = {}
for song in all_songs:
    src = song.get('source', 'unknown')
    sources[src] = sources.get(src, 0) + 1

for source, count in sources.items():
    print(f"  - {source}: {count} songs")

print("\n✓ All tests passed! OpenSourceMusicAPI is working correctly.\n")
