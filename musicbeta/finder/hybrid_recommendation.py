

from django.db.models import Q, Count, F, Case, When, IntegerField
from django.utils import timezone
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import math

from .models import (
    Song, Playlist, Genre, UserPreference, SongLike, 
    ListeningHistory, MoodPreference
)
from .recommendations import CollaborativeFiltering, ContentBasedFiltering


class UserProfiler:
    """
    Determines user profile and activity level for adaptive weighting
    """
    
    # Constants for categorization
    NEW_USER_THRESHOLD = 5  # Users with < 5 songs = new
    POWER_USER_THRESHOLD = 50  # Users with >= 50 songs = power
    MIN_HISTORY_DAYS = 30  # Days of listening history to consider
    
    @staticmethod
    def get_user_profile(user):
        """
        Classify user as 'new', 'basic', or 'power'
        Returns: dict with profile info
        """
        user_playlist_songs = Song.objects.filter(
            playlists__user=user
        ).distinct().count()
        
        user_likes = SongLike.objects.filter(user=user).count()
        total_interactions = user_playlist_songs + user_likes
        
        listening_history = ListeningHistory.objects.filter(user=user)
        history_days = 0
        if listening_history.exists():
            oldest_date = listening_history.order_by('played_at').first().played_at
            history_days = (timezone.now() - oldest_date).days
        
        completed_listens = listening_history.filter(completed=True).count()
        
        # Determine profile type
        if total_interactions < UserProfiler.NEW_USER_THRESHOLD:
            profile_type = 'new'
        elif total_interactions >= UserProfiler.POWER_USER_THRESHOLD:
            profile_type = 'power'
        else:
            profile_type = 'basic'
        
        return {
            'type': profile_type,
            'total_interactions': total_interactions,
            'playlist_songs': user_playlist_songs,
            'likes': user_likes,
            'listening_history_days': history_days,
            'completed_listens': completed_listens,
            'has_sufficient_history': total_interactions >= UserProfiler.NEW_USER_THRESHOLD,
        }
    
    @staticmethod
    def get_weights_for_profile(profile_type):
        """
        Return algorithm weights based on user profile
        Returns: dict with collaborative, content_based, contextual weights
        
        Weights always sum to 1.0
        """
        weights = {
            'new': {
                'contextual': 0.50,      # Heavy emphasis on rules
                'content_based': 0.35,   # Secondary emphasis on features
                'collaborative': 0.15,   # Minimal (not enough history)
            },
            'basic': {
                'contextual': 0.25,      # Moderate rules
                'content_based': 0.40,   # Strong content
                'collaborative': 0.35,   # Growing collaborative usage
            },
            'power': {
                'contextual': 0.15,      # Light contextual rules
                'content_based': 0.35,   # Solid content-based
                'collaborative': 0.50,   # Heavy collaborative (rich history)
            }
        }
        return weights.get(profile_type, weights['basic'])


class ContextualRulesEngine:
    """
    Knowledge-based recommendation rules without ML
    - Time-of-day logic
    - Trending songs detection
    - New album/artist releases
    - Global trending boost
    """
    
    @staticmethod
    def get_time_of_day_recommendations(limit=10):
        """
        Suggest songs based on time of day
        Morning (6am-12pm): Energetic tracks
        Afternoon (12pm-6pm): Focused/upbeat
        Evening (6pm-10pm): Mixed moods
        Night (10pm-6am): Calm/ambient
        """
        current_hour = datetime.now().hour
        
        if 6 <= current_hour < 12:  # Morning
            moods = ['energetic', 'happy']
            description = "morning energetic"
        elif 12 <= current_hour < 18:  # Afternoon
            moods = ['focus', 'energetic']
            description = "afternoon focus"
        elif 18 <= current_hour < 22:  # Evening
            moods = ['calm', 'romantic', 'happy']
            description = "evening mixed"
        else:  # Night 22:00-6:00
            moods = ['calm', 'ambient'] if current_hour >= 22 else ['calm']
            description = "night relaxation"
        
        songs = Song.objects.filter(
            Q(mood__in=moods) | Q(genre__name__iexact='ambient')
        ).distinct().order_by('-like_count', '-play_count')[:limit]
        
        return {
            'songs': list(songs),
            'rule': 'TIME_OF_DAY',
            'description': description,
            'score_boost': 0.15,  # +15% boost to these songs
        }
    
    @staticmethod
    def get_trending_songs(limit=10, days=7):
        """
        Get trending songs: recently popular across platform
        Trending = high like_count + play_count gains in last N days
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get songs with recent listening history (popularity indicator)
        trending = Song.objects.filter(
            listening_history__played_at__gte=cutoff_date
        ).annotate(
            recent_plays=Count('listening_history'),
            popularity_score=F('like_count') + (F('play_count') / 10.0)
        ).distinct().order_by('-recent_plays', '-popularity_score')[:limit]
        
        return {
            'songs': list(trending),
            'rule': 'TRENDING',
            'description': f"trending in last {days} days",
            'score_boost': 0.20,  # +20% boost to trending
        }
    
    @staticmethod
    def get_new_releases(limit=10, days=14):
        """
        Surface newly added songs (recent albums/tracks)
        Prioritizes songs added to system recently
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        
        new_releases = Song.objects.filter(
            created_at__gte=cutoff_date
        ).order_by('-created_at')[:limit]
        
        return {
            'songs': list(new_releases),
            'rule': 'NEW_RELEASES',
            'description': f"newly added ({days} days)",
            'score_boost': 0.10,  # +10% boost to new tracks
        }
    
    @staticmethod
    def get_rule_recommendations(user, limit=10):
        """
        Combine all contextual rules and return scored recommendations
        Returns list of (song, score, rule_source) tuples
        """
        rule_results = []
        
        # Collect recommendations from all rules
        time_recs = ContextualRulesEngine.get_time_of_day_recommendations(limit)
        trending_recs = ContextualRulesEngine.get_trending_songs(limit)
        new_recs = ContextualRulesEngine.get_new_releases(limit)
        
        all_rules = [time_recs, trending_recs, new_recs]
        
        song_scores = defaultdict(float)
        song_sources = defaultdict(list)
        
        for rule_batch in all_rules:
            rule_name = rule_batch['rule']
            boost = rule_batch['score_boost']
            
            for song in rule_batch['songs']:
                # Exclude songs user already has
                if not Playlist.objects.filter(user=user, songs=song).exists():
                    # Score based on rule source and its boost
                    song_scores[song.id] += boost
                    song_sources[song.id].append(rule_name)
        
        # Get the actual song objects in score order
        scored_song_ids = sorted(
            song_scores.keys(),
            key=lambda s_id: song_scores[s_id],
            reverse=True
        )[:limit]
        
        result = []
        for song_id in scored_song_ids:
            song = Song.objects.get(id=song_id)
            result.append({
                'song': song,
                'score': song_scores[song_id],
                'sources': song_sources[song_id],
            })
        
        return result


class HybridRecommendationEngine:
    @staticmethod
    def get_hybrid_recommendations(user, limit=15): 
        profile = UserProfiler.get_user_profile(user)
        weights = UserProfiler.get_weights_for_profile(profile['type'])
        collab_recs = HybridRecommendationEngine._fetch_collaborative(user)
        content_recs = HybridRecommendationEngine._fetch_content_based(user)
        contextual_recs = ContextualRulesEngine.get_rule_recommendations(user, limit * 2)
        collab_normalized = HybridRecommendationEngine._normalize_scores(collab_recs)
        content_normalized = HybridRecommendationEngine._normalize_scores(content_recs)
        contextual_normalized = HybridRecommendationEngine._normalize_scores(
            [{'song': r['song'], 'score': r['score']} for r in contextual_recs]
        )
        song_scores = defaultdict(lambda: {
            'collaborative': 0.0,
            'content_based': 0.0,
            'contextual': 0.0,
            'sources': set(),
            'reasons': set(),
            'song': None,
        })
        for item in collab_normalized:
            song_id = item['song'].id
            song_scores[song_id]['collaborative'] = item['score']
            song_scores[song_id]['sources'].add('collaborative_filtering')
            song_scores[song_id]['song'] = item['song']
            song_scores[song_id]['reasons'].add('Similar users enjoyed this')
        for item in content_normalized:
            song_id = item['song'].id
            song_scores[song_id]['content_based'] = item['score']
            song_scores[song_id]['sources'].add('content_based_filtering')
            song_scores[song_id]['song'] = item['song']
            genre_name = item.get('reason', 'matching your taste')
            song_scores[song_id]['reasons'].add(genre_name)
            
        for item in contextual_normalized:
            song_id = item['song'].id
            score = item['score']
            song_scores[song_id]['contextual'] = score
            for source in item.get('sources', []):
                song_scores[song_id]['sources'].add(f'contextual_{source}')
            song_scores[song_id]['song'] = item['song']
            if item.get('reason'):
                song_scores[song_id]['reasons'].add(item['reason'])
        final_scores = []
        for song_id, data in song_scores.items():
            if data['song'] is None:
                continue
            hybrid_score = (
                data['collaborative'] * weights['collaborative'] +
                data['content_based'] * weights['content_based'] +
                data['contextual'] * weights['contextual']
            )
            final_scores.append({
                'song': data['song'],
                'total_score': hybrid_score,
                'collaborative_score': data['collaborative'],
                'content_score': data['content_based'],
                'contextual_score': data['contextual'],
                'reasons': list(data['reasons']),
                'algorithm_sources': list(data['sources']),
            })
        final_scores.sort(key=lambda x: x['total_score'], reverse=True)
        return {
            'algorithm': 'hybrid',
            'profile': profile,
            'weights': weights,
            'recommendations': final_scores[:limit],
        }
    
    @staticmethod
    def _fetch_collaborative(user, limit=20):
        """Fetch collaborative filtering recommendations"""
        try:
            songs = CollaborativeFiltering.recommend_for_user(user, limit)
            return [{'song': s, 'score': 1.0} for s in songs]
        except Exception:
            return []
    
    @staticmethod
    def _fetch_content_based(user, limit=20):
        """Fetch content-based filtering recommendations"""
        try:
            songs = ContentBasedFiltering.recommend_for_user(user, limit)
            recommendations = ContentBasedFiltering.get_recommendations_with_scores(user, limit)
            return [
                {
                    'song': r['song'],
                    'score': r['score'] / 100.0,  # Convert from 0-100 to 0-1
                    'reason': f"Matches {', '.join(r['matched_genres'] or ['your taste'])}"
                }
                for r in recommendations
            ]
        except Exception:
            return []
    
    @staticmethod
    def _normalize_scores(items, min_score=0.0, max_score=1.0):
        """
        Normalize scores to a 0-1 range
        Handles empty or single-item lists gracefully
        """
        if not items:
            return []
        
        scores = [item.get('score', 0.0) for item in items]
        min_val = min(scores) if scores else 0.0
        max_val = max(scores) if scores else 0.0
        
        if min_val == max_val:
            # All scores are equal - assign equal weight
            return [
                {
                    **item,
                    'score': 0.5  # Mid-range score
                }
                for item in items
            ]
        
        # Normalize using min-max scaling
        range_val = max_val - min_val
        normalized = []
        for item in items:
            score = item.get('score', 0.0)
            normalized_score = (score - min_val) / range_val
            normalized.append({
                **item,
                'score': normalized_score
            })
        
        return normalized


class RecommendationExplainer:
    """
    Provides human-readable explanations for why songs were recommended
    """
    
    @staticmethod
    def get_explanation(recommendation):
        """
        Generate readable explanation from recommendation data
        """
        reasons = recommendation.get('reasons', [])
        sources = recommendation.get('algorithm_sources', [])
        
        explanation_parts = []
        
        # Translate algorithm sources
        if 'collaborative_filtering' in sources:
            explanation_parts.append("People with similar taste liked this")
        if 'content_based_filtering' in sources:
            explanation_parts.append("Matches your listening style")
        if 'contextual_trending' in sources:
            explanation_parts.append("It's trending right now")
        if 'contextual_new_releases' in sources:
            explanation_parts.append("Newly added")
        if 'contextual_time_of_day' in sources:
            hour = datetime.now().hour
            if 6 <= hour < 12:
                explanation_parts.append("Perfect for a morning listen")
            elif 18 <= hour < 22:
                explanation_parts.append("Great for evening vibes")
        
        # Add specific reasons
        explanation_parts.extend(reasons[:2])  # Limit to 2 additional reasons
        
        return " • ".join(explanation_parts[:3])  # Join top 3 reasons
