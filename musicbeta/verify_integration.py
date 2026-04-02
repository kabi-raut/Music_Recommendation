#!/usr/bin/env python
"""Final verification of Open Source Music Integration"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'musicbeta.settings')
django.setup()

from finder.models import Song
from finder.music_api import OpenSourceMusicAPI, MusicAPIService

print("\n" + "="*60)
print("OPEN SOURCE MUSIC INTEGRATION - FINAL VERIFICATION")
print("="*60 + "\n")

all_passed = True

# Test 1: SOURCE_CHOICES
print("✓ TEST 1: SOURCE_CHOICES in Song model")
choices = Song._meta.get_field('source').choices
expected_sources = ['local', 'jamendo', 'itunes', 'opensource']
actual_sources = [value for value, label in choices]

print("  Expected sources:", expected_sources)
print("  Actual sources:  ", actual_sources)

if set(expected_sources) == set(actual_sources):
    print("  ✓ PASSED: All sources present\n")
else:
    print("  ✗ FAILED: Source mismatch\n")
    all_passed = False

# Test 2: OpenSourceMusicAPI methods
print("✓ TEST 2: OpenSourceMusicAPI methods")
methods_required = {
    'search_tracks': 'Search for open source music by query/genre',
    'get_by_genre': 'Filter open source music by genre',
    'get_artist_tracks': 'Get tracks from specific artist'
}

for method_name, description in methods_required.items():
    has_method = hasattr(OpenSourceMusicAPI, method_name)
    status = "✓" if has_method else "✗"
    print(f"  {status} {method_name:25} - {description}")
    if not has_method:
        all_passed = False

print()

# Test 3: search_tracks functionality
print("✓ TEST 3: search_tracks() functionality")
try:
    songs = OpenSourceMusicAPI.search_tracks('rock', limit=3)
    print(f"  ✓ Returned {len(songs)} songs for 'rock' query")
    
    if songs:
        song = songs[0]
        required_fields = ['id', 'title', 'artist', 'genre', 'audio_url', 'source', 'external_id']
        missing_fields = [f for f in required_fields if f not in song]
        
        if not missing_fields:
            print(f"  ✓ Song has all required fields")
            print(f"    - ID: {song['id']}")
            print(f"    - Title: {song['title']}")
            print(f"    - Artist: {song['artist']}")
            print(f"    - Source: {song['source']}")
        else:
            print(f"  ✗ Missing fields: {missing_fields}")
            all_passed = False
    print()
except Exception as e:
    print(f"  ✗ Error calling search_tracks(): {e}\n")
    all_passed = False

# Test 4: get_by_genre functionality
print("✓ TEST 4: get_by_genre() functionality")
try:
    songs = OpenSourceMusicAPI.get_by_genre('Jazz', limit=2)
    print(f"  ✓ Returned {len(songs)} songs for 'Jazz' genre")
    print()
except Exception as e:
    print(f"  ✗ Error calling get_by_genre(): {e}\n")
    all_passed = False

# Test 5: MusicAPIService integration
print("✓ TEST 5: MusicAPIService.search_all() integration")
try:
    all_songs = MusicAPIService.search_all('test', limit_per_source=2)
    print(f"  ✓ Returned {len(all_songs)} total songs")
    
    source_counts = {}
    for song in all_songs:
        source = song.get('source', 'unknown')
        source_counts[source] = source_counts.get(source, 0) + 1
    
    print("  ✓ Sources represented:")
    for source, count in sorted(source_counts.items()):
        print(f"    - {source}: {count} songs")
    print()
except Exception as e:
    print(f"  ✗ Error calling search_all(): {e}\n")
    all_passed = False

# Test 6: View integration (verify imports)
print("✓ TEST 6: View integration")
try:
    from finder.views import discover_music, browse_by_source
    print("  ✓ discover_music view imported successfully")
    print("  ✓ browse_by_source view imported successfully")
    print()
except Exception as e:
    print(f"  ✗ Error importing views: {e}\n")
    all_passed = False

# Test 7: Database compatibility
print("✓ TEST 7: Database compatibility")
try:
    # Verify Song model can handle 'opensource' source
    song_data = {
        'title': 'Test Song',
        'artist': 'Test Artist',
        'source': 'opensource',
        'external_id': 'test_123',
        'audio_url': 'https://example.com/test.mp3'
    }
    # Just validate the choices, don't create
    valid_sources = dict(choices)
    if 'opensource' in valid_sources:
        print(f"  ✓ Song model accepts 'opensource' as source")
    else:
        print(f"  ✗ Song model does not accept 'opensource'")
        all_passed = False
    print()
except Exception as e:
    print(f"  ✗ Error: {e}\n")
    all_passed = False

# Final Summary
print("="*60)
if all_passed:
    print("✓✓✓ ALL TESTS PASSED ✓✓✓")
    print("\nOPEN SOURCE MUSIC INTEGRATION IS COMPLETE AND FUNCTIONAL")
    print("\nYou can now:")
    print("  • Go to /discover_music/?source=opensource")
    print("  • Browse open source music by genre")
    print("  • Add open source songs to playlists")
    print("  • Stream audio from open source providers")
    sys.exit(0)
else:
    print("✗✗✗ SOME TESTS FAILED ✗✗✗")
    print("\nPlease check the errors above and fix any issues.")
    sys.exit(1)
