"""
API views for new music streaming features:
- Like/Favorite system
- Listening history tracking
- Mood-based recommendations
- Advanced search
- Playlist sharing
"""

from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, F
from django.utils import timezone
from datetime import timedelta

from .models import (
    Song, SongLike, ListeningHistory, MoodPreference, 
    Playlist, Subscription, RecommendationCache, RecommendationOverride
)
from .hybrid_recommendation import HybridRecommendationEngine, RecommendationExplainer


@login_required
@require_POST
def like_song(request):
    """Like/favorite a song"""
    song_id = request.POST.get('song_id')
    song = get_object_or_404(Song, id=song_id)

    # Likes are only allowed for songs already present in one of the user's playlists.
    in_user_playlist = Playlist.objects.filter(user=request.user, songs=song).exists()
    existing_like = SongLike.objects.filter(user=request.user, song=song).first()

    if existing_like and not in_user_playlist:
        existing_like.delete()
        Song.objects.filter(id=song_id).update(like_count=F('like_count') - 1)
        return JsonResponse({
            'status': 'success',
            'action': 'unliked',
            'message': f'Removed "{song.title}" from favorites'
        })

    if not in_user_playlist:
        return JsonResponse({
            'status': 'error',
            'message': 'You can only like songs that are already in one of your playlists.'
        }, status=400)
    
    like, created = SongLike.objects.get_or_create(
        user=request.user,
        song=song
    )
    
    if not created:
        like.delete()
        Song.objects.filter(id=song_id).update(like_count=F('like_count') - 1)
        return JsonResponse({
            'status': 'success',
            'action': 'unliked',
            'message': f'Removed "{song.title}" from favorites'
        })
    
    Song.objects.filter(id=song_id).update(like_count=F('like_count') + 1)
    return JsonResponse({
        'status': 'success',
        'action': 'liked',
        'message': f'Added "{song.title}" to favorites'
    })


@login_required
@require_GET
def get_user_likes(request):
    """Get all liked songs for current user"""
    liked_songs = Song.objects.filter(
        liked_by_users__user=request.user
    ).values('id', 'title', 'artist', 'mood', 'source').distinct()
    
    return JsonResponse({
        'status': 'success',
        'count': liked_songs.count(),
        'songs': list(liked_songs)
    })


@login_required
@require_POST
def track_listening(request):
    """Track song listening"""
    song_id = request.POST.get('song_id')
    duration_played = int(request.POST.get('duration_played', 0))
    completed = request.POST.get('completed', 'false').lower() == 'true'
    
    song = get_object_or_404(Song, id=song_id)
    
    history = ListeningHistory.objects.create(
        user=request.user,
        song=song,
        duration_played=duration_played,
        completed=completed
    )
    
    # Update song play count
    if completed:
        Song.objects.filter(id=song_id).update(play_count=F('play_count') + 1)
    
    return JsonResponse({
        'status': 'success',
        'message': 'Listening tracked'
    })


@login_required
@require_POST
def set_mood_preference(request):
    """Set user mood preference"""
    mood = request.POST.get('mood')
    score = float(request.POST.get('score', 0.5))
    
    VALID_MOODS = ['happy', 'sad', 'focus', 'energetic', 'calm', 'romantic']
    if mood not in VALID_MOODS:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid mood'
        }, status=400)
    
    pref, _ = MoodPreference.objects.get_or_create(
        user=request.user,
        mood=mood
    )
    pref.preference_score = min(max(score, 0), 1)
    pref.save()
    
    return JsonResponse({
        'status': 'success',
        'message': f'Mood preference "{mood}" updated'
    })


@login_required
@require_GET
def get_recently_played(request):
    """Get recently played songs"""
    limit = int(request.GET.get('limit', 20))
    
    songs = Song.objects.filter(
        listening_history__user=request.user
    ).annotate(
        last_played=F('listening_history__played_at')
    ).order_by('-listening_history__played_at').distinct()[:limit]
    
    return JsonResponse({
        'status': 'success',
        'count': songs.count(),
        'songs': [{
            'id': s.id,
            'title': s.title,
            'artist': s.artist,
            'mood': s.mood
        } for s in songs]
    })


@login_required
@require_GET
def get_most_played(request):
    """Get most played songs"""
    limit = int(request.GET.get('limit', 20))
    
    songs = Song.objects.filter(
        listening_history__user=request.user,
        listening_history__completed=True
    ).annotate(
        plays=Count('listening_history')
    ).order_by('-plays')[:limit]
    
    return JsonResponse({
        'status': 'success',
        'count': songs.count(),
        'songs': [{
            'id': s.id,
            'title': s.title,
            'artist': s.artist,
            'plays': s.plays
        } for s in songs]
    })


@login_required
@require_GET
def search_advanced(request):
    """Advanced search with multiple filters"""
    query = request.GET.get('q', '').strip()
    genre = request.GET.get('genre', '').strip()
    artist = request.GET.get('artist', '').strip()
    mood = request.GET.get('mood', '').strip()
    sort_by = request.GET.get('sort', 'title')  # title, popularity, recent
    
    songs = Song.objects.all()
    
    if query:
        songs = songs.filter(
            Q(title__icontains=query) |
            Q(artist__icontains=query) |
            Q(genre_name__icontains=query)
        )
    
    if genre:
        songs = songs.filter(
            Q(genre__name__icontains=genre) |
            Q(genre_name__icontains=genre)
        )
    
    if artist:
        songs = songs.filter(artist__icontains=artist)
    
    if mood:
        songs = songs.filter(mood=mood)
    
    # Sorting
    if sort_by == 'popularity':
        songs = songs.order_by('-play_count', '-like_count')
    elif sort_by == 'recent':
        songs = songs.order_by('-created_at')
    else:
        songs = songs.order_by('title')
    
    limit = int(request.GET.get('limit', 50))
    songs = songs[:limit]
    
    return JsonResponse({
        'status': 'success',
        'count': songs.count(),
        'songs': [{
            'id': s.id,
            'title': s.title,
            'artist': s.artist,
            'genre': s.get_genre_display(),
            'mood': s.mood,
            'play_count': s.play_count,
            'like_count': s.like_count
        } for s in songs]
    })


@login_required
def get_playlist_share_link(request, playlist_id):
    """Generate or retrieve playlist share link"""
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    subscription = Subscription.objects.get_or_create(user=request.user)[0]

    if not subscription.can_share_playlists():
        return JsonResponse({
            'status': 'error',
            'message': 'Playlist sharing requires an active premium subscription.'
        }, status=403)
    
    playlist.generate_share_link()
    
    return JsonResponse({
        'status': 'success',
        'playlist_id': playlist.id,
        'share_link': playlist.share_link,
        'is_public': playlist.is_public,
        'full_url': request.build_absolute_uri(f'/playlist/share/{playlist.share_link}/')
    })


@login_required
@require_POST
def toggle_playlist_visibility(request, playlist_id):
    """Toggle playlist public/private"""
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    subscription = Subscription.objects.get_or_create(user=request.user)[0]

    if not subscription.can_share_playlists():
        return JsonResponse({
            'status': 'error',
            'message': 'Playlist sharing requires an active premium subscription.'
        }, status=403)
    
    playlist.is_public = not playlist.is_public
    if playlist.is_public:
        playlist.generate_share_link()
    
    playlist.save()
    
    return JsonResponse({
        'status': 'success',
        'is_public': playlist.is_public,
        'message': f'Playlist is now {"public" if playlist.is_public else "private"}'
    })


@login_required
def get_listening_time_stats(request):
    """Get user listening statistics"""
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    today_plays = ListeningHistory.objects.filter(
        user=request.user,
        completed=True,
        played_at__date=today
    ).count()
    
    week_plays = ListeningHistory.objects.filter(
        user=request.user,
        completed=True,
        played_at__date__gte=week_ago
    ).count()
    
    month_plays = ListeningHistory.objects.filter(
        user=request.user,
        completed=True,
        played_at__date__gte=month_ago
    ).count()
    
    # Most played genres
    top_genres = Song.objects.filter(
        listening_history__user=request.user,
        listening_history__completed=True
    ).values('genre_name').annotate(
        count=Count('listening_history')
    ).order_by('-count')[:5]
    
    return JsonResponse({
        'status': 'success',
        'stats': {
            'today_plays': today_plays,
            'week_plays': week_plays,
            'month_plays': month_plays,
            'top_genres': list(top_genres)
        }
    })


@login_required
def get_personalized_recommendations(request):
    """
    Get hybrid recommendations combining collaborative filtering, content-based filtering,
    and contextual rules with adaptive weighting based on user profile.
    
    - New Users: Weighted towards contextual rules + content-based filtering
    - Power Users: Weighted towards collaborative filtering + content-based filtering
    """
    limit = int(request.GET.get('limit', 15))
    subscription = Subscription.objects.get_or_create(user=request.user)[0]

    if not subscription.can_use_advanced_recommendations():
        return JsonResponse({
            'status': 'error',
            'message': 'Advanced recommendations require an active premium subscription.'
        }, status=403)

    if not Playlist.objects.filter(user=request.user).exists():
        return JsonResponse({
            'status': 'success',
            'algorithm': 'hybrid_enhanced',
            'user_profile': None,
            'algorithm_weights': None,
            'explanation': 'No recommendations yet because no playlists exist.',
            'count': 0,
            'songs': [],
            'message': 'You have no playlists. Search songs or create a playlist to get recommendations.'
        })
    
    try:
        # Get hybrid recommendations using all three algorithms
        hybrid_result = HybridRecommendationEngine.get_hybrid_recommendations(
            request.user,
            limit=limit
        )
        
        # Prepend active manual overrides (user-specific + global) at the top
        overrides = RecommendationOverride.objects.filter(
            is_active=True
        ).filter(
            Q(user=request.user) | Q(user__isnull=True)
        ).select_related('recommended_song').order_by('-created_at')[:3]
        
        override_ids = set()
        override_list = []
        for override in overrides:
            if override.recommended_song and override.recommended_song.id not in override_ids:
                override_ids.add(override.recommended_song.id)
                override_list.append({
                    'id': override.recommended_song.id,
                    'title': override.recommended_song.title,
                    'artist': override.recommended_song.artist,
                    'genre': override.recommended_song.get_genre_display(),
                    'mood': override.recommended_song.mood,
                    'audio_url': override.recommended_song.get_audio_source(),
                    'cover_image': override.recommended_song.get_cover_image(),
                    'total_score': 1.0,  # Manual picks score highest
                    'explanation': 'Handpicked for you',
                    'algorithm_sources': ['admin_curated'],
                })
        
        # Add hybrid recommendations (excluding manual overrides)
        recommendation_list = []
        for rec in hybrid_result['recommendations']:
            if rec['song'].id not in override_ids:
                explanation = RecommendationExplainer.get_explanation(rec)
                recommendation_list.append({
                    'id': rec['song'].id,
                    'title': rec['song'].title,
                    'artist': rec['song'].artist,
                    'genre': rec['song'].get_genre_display(),
                    'mood': rec['song'].mood,
                    'audio_url': rec['song'].get_audio_source(),
                    'cover_image': rec['song'].get_cover_image(),
                    'total_score': round(rec['total_score'], 3),
                    'collaborative_score': round(rec['collaborative_score'], 3),
                    'content_score': round(rec['content_score'], 3),
                    'contextual_score': round(rec['contextual_score'], 3),
                    'explanation': explanation,
                    'algorithm_sources': rec['algorithm_sources'],
                })
        
        # Combine: manual overrides first, then hybrid recommendations
        combined = override_list + recommendation_list
        combined = combined[:limit]
        
        # Build profile explanation
        profile = hybrid_result['profile']
        profile_descriptions = {
            'new': 'You\'re new to the platform — recommendations emphasize trending music and personalized suggestions',
            'basic': 'You have some listening history — recommendations blend trends with your established taste',
            'power': 'You\'re an active user — recommendations prioritize songs similar users loved and match your taste'
        }
        
        return JsonResponse({
            'status': 'success',
            'algorithm': 'hybrid_enhanced',
            'user_profile': {
                'type': profile['type'],
                'total_interactions': profile['total_interactions'],
                'description': profile_descriptions.get(profile['type'], ''),
            },
            'algorithm_weights': hybrid_result['weights'],
            'explanation': 'Personalized using collaborative filtering, content analysis, and trending insights',
            'count': len(combined),
            'songs': combined
        })
    
    except Exception as e:
        # Fallback to basic recommendations if hybrid engine fails
        return JsonResponse({
            'status': 'error',
            'message': f'Could not generate recommendations: {str(e)}',
            'fallback': True
        }, status=500)


