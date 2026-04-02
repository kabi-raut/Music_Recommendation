"""
Example Usage Patterns for Recommendation Algorithms

This file demonstrates various ways to use the recommendation system
in your Django application.
"""

from finder.recommendations import (
    CollaborativeFiltering,
    ContentBasedFiltering,
    HybridRecommendation,
    RecommendationScorer
)
from finder.models import Playlist, Song
from django.contrib.auth.models import User


# ==================== EXAMPLE 1: BASIC USAGE ====================

def example_basic_usage(user):
    """Get basic recommendations using each algorithm"""
    
    # Collaborative Filtering - Based on similar users
    collab_songs = CollaborativeFiltering.recommend_for_user(user, limit=10)
    print(f"Collaborative: Got {collab_songs.count()} recommendations")
    
    # Content-Based Filtering - Based on song features
    content_songs = ContentBasedFiltering.recommend_for_user(user, limit=10)
    print(f"Content-based: Got {content_songs.count()} recommendations")
    
    # Hybrid (Default 50/50 split)
    hybrid_songs = HybridRecommendation.recommend_for_user(user, limit=10)
    print(f"Hybrid: Got {len(hybrid_songs)} recommendations")


# ==================== EXAMPLE 2: CUSTOM WEIGHTS ====================

def example_custom_weights(user):
    """Hybrid recommendations with custom algorithm weights"""
    
    # Favor collaborative filtering (60% vs 40% content)
    songs_collab_heavy = HybridRecommendation.recommend_for_user(
        user,
        limit=10,
        collaborative_weight=0.6,
        content_weight=0.4
    )
    
    # Favor content-based filtering (30% collab vs 70% content)
    songs_content_heavy = HybridRecommendation.recommend_for_user(
        user,
        limit=10,
        collaborative_weight=0.3,
        content_weight=0.7
    )
    
    return songs_collab_heavy, songs_content_heavy


# ==================== EXAMPLE 3: SIMILAR USERS ====================

def example_find_similar_users(user):
    """Find users with similar musical taste"""
    
    similar_users = CollaborativeFiltering.get_similar_users(user, limit=5)
    
    for similar_user in similar_users:
        print(f"Found similar user: {similar_user.username}")
        
        # Get their playlists
        playlists = Playlist.objects.filter(user=similar_user)
        for playlist in playlists:
            print(f"  - Playlist: {playlist.name}")


# ==================== EXAMPLE 4: COMPARE ALGORITHMS ====================

def example_compare_algorithms(user):
    """Compare recommendations from all three algorithms"""
    
    collab = set(CollaborativeFiltering.recommend_for_user(user).values_list('id', flat=True))
    content = set(ContentBasedFiltering.recommend_for_user(user).values_list('id', flat=True))
    hybrid = set(s.id for s in HybridRecommendation.recommend_for_user(user))
    
    print(f"Collaborative: {len(collab)} recommendations")
    print(f"Content-based: {len(content)} recommendations")
    print(f"Hybrid: {len(hybrid)} recommendations")
    
    print(f"\nAgreement between algorithms:")
    print(f"Collab ∩ Content: {len(collab & content)} songs")
    print(f"Collab ∩ Hybrid: {len(collab & hybrid)} songs")
    print(f"Content ∩ Hybrid: {len(content & hybrid)} songs")
    print(f"All three agree: {len(collab & content & hybrid)} songs")


# ==================== EXAMPLE 5: SCORING & RANKING ====================

def example_scoring_and_ranking(user):
    """Use helper utilities to score recommendations"""
    
    # Get base recommendations
    songs = HybridRecommendation.recommend_for_user(user, limit=20)
    songs_queryset = Song.objects.filter(
        id__in=[s.id for s in songs]
    )
    
    # Rank by popularity (most playlists)
    popular = RecommendationScorer.score_by_popularity(songs_queryset)
    print("Most popular recommendations:")
    for song in popular[:3]:
        print(f"  - {song.title}")
    
    # Rank by recency (newest songs)
    recent = RecommendationScorer.score_by_recency(songs_queryset)
    print("\nNewest recommendations:")
    for song in recent[:3]:
        print(f"  - {song.title}")
    
    # Rank by genre diversity
    diverse = RecommendationScorer.score_by_genre_diversity(
        songs_queryset,
        target_count=10
    )
    print("\nDiverse (varied genres) recommendations:")
    for song in diverse:
        print(f"  - {song.title} ({song.get_genre_display()})")


# ==================== EXAMPLE 6: UNIVERSAL METHOD ====================

def example_universal_method(user):
    """Use the universal get_personalized_recommendations method"""
    
    # All three methods through one interface
    songs_collab = HybridRecommendation.get_personalized_recommendations(
        user,
        method='collaborative',
        limit=10
    )
    
    songs_content = HybridRecommendation.get_personalized_recommendations(
        user,
        method='content',
        limit=10
    )
    
    songs_hybrid = HybridRecommendation.get_personalized_recommendations(
        user,
        method='hybrid',
        limit=10
    )
    
    print(f"Collaborative: {len(songs_collab)} songs")
    print(f"Content-based: {len(songs_content)} songs")
    print(f"Hybrid: {len(songs_hybrid)} songs")


# ==================== EXAMPLE 7: BATCH PROCESSING ====================

def example_batch_update_all_users():
    """Generate recommendations for all users (useful for caching/precomputing)"""
    
    from django.core.cache import cache
    
    all_users = User.objects.all()
    
    for user in all_users:
        # Precompute recommendations for each user
        cache_key = f'recommendations_{user.id}_hybrid'
        
        # Check if already cached
        if not cache.get(cache_key):
            recommendations = HybridRecommendation.recommend_for_user(
                user,
                limit=15
            )
            
            # Cache for 24 hours
            cache.set(cache_key, recommendations, 60 * 60 * 24)
            print(f"Generated recommendations for {user.username}")


# ==================== EXAMPLE 8: A/B TESTING ====================

def example_ab_testing(user):
    """Test different weight combinations for A/B testing"""
    
    weight_configs = [
        (0.5, 0.5, "Balanced"),
        (0.6, 0.4, "Collab-Heavy"),
        (0.4, 0.6, "Content-Heavy"),
        (0.7, 0.3, "Strong Collab"),
        (0.3, 0.7, "Strong Content"),
    ]
    
    for collab, content, label in weight_configs:
        songs = HybridRecommendation.recommend_for_user(
            user,
            limit=10,
            collaborative_weight=collab,
            content_weight=content
        )
        
        print(f"{label} ({collab:.0%} / {content:.0%}): {len(songs)} recommendations")
        
        # You could save results for comparison
        # ResultsModel.objects.create(
        #     user=user,
        #     method='hybrid',
        #     config=label,
        #     recommendation_count=len(songs)
        # )


# ==================== EXAMPLE 9: COLD START HANDLING ====================

def example_cold_start_handling(new_user):
    """Handle new users with no playlist history"""
    
    # Check if user has any playlists
    playlist_count = Playlist.objects.filter(user=new_user).count()
    
    if playlist_count == 0:
        print("New user with no playlists - using content-based with preferred genres")
        
        # ContentBasedFiltering handles this automatically by falling back
        # to recommend_by_preferred_genres or recent songs
        recommendations = ContentBasedFiltering.recommend_for_user(
            new_user,
            limit=10
        )
    else:
        print(f"User has {playlist_count} playlists - using full hybrid approach")
        recommendations = HybridRecommendation.recommend_for_user(
            new_user,
            limit=10
        )
    
    return recommendations


# ==================== EXAMPLE 10: SONG SIMILARITY ====================

def example_song_similarity():
    """Find songs similar to a specific song"""
    
    target_song = Song.objects.first()
    
    if target_song:
        all_songs = Song.objects.exclude(id=target_song.id)
        
        similarities = []
        for candidate_song in all_songs:
            similarity = ContentBasedFiltering.calculate_similarity(
                target_song,
                candidate_song
            )
            if similarity > 0:
                similarities.append((candidate_song, similarity))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        print(f"Songs most similar to '{target_song.title}':")
        for song, score in similarities[:5]:
            print(f"  - {song.title} (similarity: {score:.2%})")


# ==================== EXAMPLE 11: DJANGO SHELL USAGE ====================

"""
To use these in Django shell:

$ python manage.py shell

>>> from finder.models import User
>>> from examples import example_basic_usage
>>> 
>>> user = User.objects.first()
>>> example_basic_usage(user)

Collaborative: Got 5 recommendations
Content-based: Got 3 recommendations
Hybrid: Got 8 recommendations
"""


# ==================== EXAMPLE 12: CUSTOM VIEW ====================

"""
Add to your views.py:

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from finder.recommendations import HybridRecommendation

@login_required
def smart_recommendations(request):
    # Get custom weight from user preference
    collab_weight = request.GET.get('collab', 0.5)
    content_weight = request.GET.get('content', 0.5)
    
    recommendations = HybridRecommendation.recommend_for_user(
        request.user,
        limit=20,
        collaborative_weight=float(collab_weight),
        content_weight=float(content_weight)
    )
    
    return render(request, 'recommendations.html', {
        'songs': recommendations,
        'collab_weight': collab_weight,
        'content_weight': content_weight,
    })

# Add to urls.py:
path('smart-recommendations/', smart_recommendations, name='smart_recommendations')
"""


# ==================== EXAMPLE 13: API INTEGRATION ====================

"""
To fetch recommendations via JavaScript:

// Basic hybrid recommendations
fetch('/api/recommendations/?method=hybrid&limit=15')
  .then(r => r.json())
  .then(data => {
    console.log(`Got ${data.count} recommendations`);
    data.songs.forEach(song => {
      console.log(`${song.title} by ${song.artist}`);
    });
  });

// Collaborative filtering
fetch('/api/recommendations/?method=collaborative&limit=10')
  .then(r => r.json())
  .then(data => displaySongs(data.songs));

// Custom hybrid weights
fetch('/api/recommendations/?method=hybrid&collab_weight=0.6&content_weight=0.4')
  .then(r => r.json())
  .then(data => displaySongs(data.songs));
"""


# ==================== PERFORMANCE TIPS ====================

"""
OPTIMIZATION TIPS:

1. Cache Results:
   from django.core.cache import cache
   key = f'recommendations_{user.id}_hybrid'
   cache.set(key, songs, 3600)  # Cache for 1 hour

2. Limit Database Queries:
   - Algorithms already use select_related() and prefetch_related()
   - Consider using .only() to limit fields loaded

3. Batch Processing:
   - Pre-compute recommendations for active users
   - Update cache hourly/daily instead of on-demand

4. Add Database Indexes:
   class Song(models.Model):
       class Meta:
           indexes = [
               models.Index(fields=['genre', 'created_at']),
               models.Index(fields=['artist', 'genre']),
           ]

5. Consider Pagination:
   - Don't load all recommendations at once
   - Use Django's Paginator for large result sets
"""
