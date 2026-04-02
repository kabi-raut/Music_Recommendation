"""
Recommendation System for Music Discovery
Implements recommendation algorithms:
1. Collaborative Filtering - Based on similar users' preferences
2. Content-Based Filtering - Based on song features (genre, artist)
"""

from django.db.models import Q, Count, F, Case, When, IntegerField
from .models import Song, Playlist, Genre, UserPreference
from .music_api import OpenSourceMusicAPI
from django.contrib.auth.models import User
from collections import Counter, defaultdict


class CollaborativeFiltering:
    """
    Collaborative Filtering Algorithm
    Recommends songs based on what similar users liked
    """

    # Shared-song overlap should matter more than shared genres.
    SHARED_SONG_WEIGHT = 5
    SHARED_GENRE_WEIGHT = 1
    
    @staticmethod
    def get_similar_users(user, limit=5):
        """
        Find users with similar taste by analyzing their playlists
        Similarity is based on shared songs and genres
        """
        user_playlists = Playlist.objects.filter(user=user)
        user_songs = Song.objects.filter(playlists__in=user_playlists).distinct()
        user_genres = Genre.objects.filter(song__in=user_songs).distinct()
        
        if not user_songs.exists():
            return User.objects.none()
        
        # Find users who have songs or genres in common.
        # Rank by actual overlap instead of total library size so large playlists
        # do not dominate the results.
        similar_users = (
            User.objects.exclude(id=user.id)
            .annotate(
                shared_song_count=Count(
                    'playlist__songs',
                    filter=Q(playlist__songs__in=user_songs),
                    distinct=True,
                ),
                shared_genre_count=Count(
                    'userpreference__liked_genres',
                    filter=Q(userpreference__liked_genres__in=user_genres),
                    distinct=True,
                ),
                similarity_score=(
                    Count(
                        'playlist__songs',
                        filter=Q(playlist__songs__in=user_songs),
                        distinct=True,
                    ) * CollaborativeFiltering.SHARED_SONG_WEIGHT
                ) + (
                    Count(
                        'userpreference__liked_genres',
                        filter=Q(userpreference__liked_genres__in=user_genres),
                        distinct=True,
                    ) * CollaborativeFiltering.SHARED_GENRE_WEIGHT
                ),
            )
            .filter(Q(shared_song_count__gt=0) | Q(shared_genre_count__gt=0))
            .order_by('-similarity_score', '-shared_song_count', '-shared_genre_count', 'username')[:limit]
        )
        
        return similar_users
    
    @staticmethod
    def recommend_for_user(user, limit=10):
        """
        Recommend songs based on what similar users liked
        Returns songs that the user hasn't added to any playlist yet
        """
        # Get songs the user already has
        user_songs = Song.objects.filter(
            playlists__user=user
        ).values_list('id', flat=True)
        
        # Get similar users
        similar_users = list(CollaborativeFiltering.get_similar_users(user, limit=10))
        
        if not similar_users:
            return ContentBasedFiltering.recommend_by_preferred_genres(user, limit)
        
        user_song_ids = set(user_songs)
        song_scores = defaultdict(float)
        song_popularity = defaultdict(int)

        # Give more weight to songs from users who overlap more with the current user.
        for similar_user in similar_users:
            shared_song_count = getattr(similar_user, 'shared_song_count', 0)
            shared_genre_count = getattr(similar_user, 'shared_genre_count', 0)
            similarity_weight = (
                (shared_song_count * CollaborativeFiltering.SHARED_SONG_WEIGHT)
                + (shared_genre_count * CollaborativeFiltering.SHARED_GENRE_WEIGHT)
            )

            if similarity_weight <= 0:
                continue

            similar_user_songs = Song.objects.filter(
                playlists__user=similar_user
            ).exclude(
                id__in=user_song_ids
            ).distinct()

            for song in similar_user_songs:
                song_scores[song.id] += similarity_weight
                song_popularity[song.id] += 1

        if not song_scores:
            return ContentBasedFiltering.recommend_by_preferred_genres(user, limit)

        ranked_song_ids = sorted(
            song_scores.keys(),
            key=lambda song_id: (song_scores[song_id], song_popularity[song_id]),
            reverse=True,
        )[:limit]

        preserved_order = Case(
            *[When(id=song_id, then=position) for position, song_id in enumerate(ranked_song_ids)],
            output_field=IntegerField(),
        )

        recommended_songs = Song.objects.filter(id__in=ranked_song_ids).order_by(preserved_order)
        
        return recommended_songs


class ContentBasedFiltering:
    """
    Content-Based Filtering Algorithm
    Recommends songs based on features like genre, artist, source, and duration
    """
    
    @staticmethod
    def get_song_features(song):
        """Extract comprehensive features from a song for comparison"""
        return {
            'genre': song.genre_id,
            'genre_name': song.get_genre_display(),
            'artist': song.artist.lower().strip() if song.artist else '',
            'title': song.title.lower().strip() if song.title else '',
            'source': song.source,
            'duration': song.duration or 0,
        }
    
    @staticmethod
    def calculate_similarity(song1, song2):
        """
        Calculate similarity between two songs
        Weights: Genre (50%), Artist (30%), Source (10%), Duration (10%)
        """
        feat1 = ContentBasedFiltering.get_song_features(song1)
        feat2 = ContentBasedFiltering.get_song_features(song2)
        
        similarity = 0.0
        
        # Genre similarity (50% weight) - strongest indicator
        if feat1['genre'] and feat2['genre'] and feat1['genre'] == feat2['genre']:
            similarity += 0.50
        elif feat1['genre_name'] and feat2['genre_name']:
            # Partial credit for similar genre names (even if different IDs)
            if feat1['genre_name'].lower() in feat2['genre_name'].lower() or feat2['genre_name'].lower() in feat1['genre_name'].lower():
                similarity += 0.25
        
        # Artist similarity (30% weight) - same artist is highly relevant
        if feat1['artist'] and feat2['artist']:
            if feat1['artist'] == feat2['artist']:
                similarity += 0.30
            elif feat1['artist'] in feat2['artist'] or feat2['artist'] in feat1['artist']:
                similarity += 0.15  # Partial credit for containing artist name
        
        # Source similarity (10% weight) - maintains consistency
        if feat1['source'] == feat2['source']:
            similarity += 0.10
        
        # Duration similarity (10% weight) - similar length songs
        if feat1['duration'] > 0 and feat2['duration'] > 0:
            duration_diff = abs(feat1['duration'] - feat2['duration'])
            # If duration is within 30 seconds, give full credit
            if duration_diff <= 30:
                similarity += 0.10
            # Partial credit if within 60 seconds
            elif duration_diff <= 60:
                similarity += 0.05
        
        return similarity
    
    @staticmethod
    def recommend_for_user(user, limit=10):
        """
        Recommend songs based on user's playlist content
        Finds songs similar to what user already has - enhanced algorithm
        """
        # Get user's playlist songs
        user_songs = Song.objects.filter(
            playlists__user=user
        ).distinct()
        
        if not user_songs.exists():
            # If no playlists, recommend popular songs from favorite genres
            return ContentBasedFiltering.recommend_by_preferred_genres(user, limit)
        
        # Get all other songs
        all_songs = Song.objects.all()
        user_song_ids = user_songs.values_list('id', flat=True)
        candidate_songs = all_songs.exclude(id__in=user_song_ids)
        
        if not candidate_songs.exists():
            return Song.objects.none()
        
        # Calculate similarity for each candidate
        song_similarities = []
        user_songs_sample = list(user_songs[:15])  # Use up to 15 user songs for comparison
        
        for candidate in candidate_songs:
            total_similarity = 0.0
            max_possible_score = len(user_songs_sample)
            
            for user_song in user_songs_sample:
                similarity = ContentBasedFiltering.calculate_similarity(user_song, candidate)
                total_similarity += similarity
            
            # Normalize by number of comparisons
            if max_possible_score > 0:
                avg_similarity = total_similarity / max_possible_score
                if avg_similarity > 0.15:  # Only recommend if meaningful similarity
                    song_similarities.append((candidate, avg_similarity))
        
        # Sort by similarity (descending) and return top recommendations
        song_similarities.sort(key=lambda x: x[1], reverse=True)
        recommended_songs = [song for song, score in song_similarities[:limit]]
        
        if recommended_songs:
            return Song.objects.filter(id__in=[s.id for s in recommended_songs])
        
        return Song.objects.none()
    
    @staticmethod
    def get_recommendations_with_scores(user, limit=10):
        """
        Get recommendations along with similarity scores for display
        Useful for showing why a song was recommended
        """
        user_songs = Song.objects.filter(playlists__user=user).distinct()
        
        if not user_songs.exists():
            return []
        
        all_songs = Song.objects.all()
        user_song_ids = user_songs.values_list('id', flat=True)
        candidate_songs = all_songs.exclude(id__in=user_song_ids)
        
        song_similarities = []
        user_songs_sample = list(user_songs[:15])
        
        for candidate in candidate_songs:
            total_similarity = 0.0
            matched_genres = set()
            matched_artists = set()
            
            for user_song in user_songs_sample:
                similarity = ContentBasedFiltering.calculate_similarity(user_song, candidate)
                total_similarity += similarity
                
                # Track what matched
                if user_song.get_genre_display() == candidate.get_genre_display():
                    matched_genres.add(user_song.get_genre_display())
                if user_song.artist and user_song.artist.lower() == candidate.artist.lower():
                    matched_artists.add(user_song.artist)
            
            if len(user_songs_sample) > 0:
                avg_similarity = total_similarity / len(user_songs_sample)
                if avg_similarity > 0.15:
                    song_similarities.append({
                        'song': candidate,
                        'score': round(avg_similarity * 100, 1),
                        'matched_genres': list(matched_genres),
                        'matched_artists': list(matched_artists),
                    })
        
        song_similarities.sort(key=lambda x: x['score'], reverse=True)
        return song_similarities[:limit]
    
    @staticmethod
    def recommend_by_preferred_genres(user, limit=10):
        """Recommend songs from user's preferred genres or open-source music for cold-start users"""
        if not Playlist.objects.filter(user=user).exists():
            return ContentBasedFiltering.recommend_open_source_cold_start(limit)

        try:
            user_pref = UserPreference.objects.get(user=user)
            genres = user_pref.liked_genres.all()
            
            if genres.exists():
                return Song.objects.filter(
                    genre__in=genres
                ).order_by('-created_at')[:limit]
        except UserPreference.DoesNotExist:
            pass
        
        # If no preferences, return recently added songs from popular genres
        return Song.objects.all().order_by('-created_at')[:limit]

    @staticmethod
    def recommend_open_source_cold_start(limit=10):
        """Return a database queryset of open-source songs for users with no playlist history."""
        tracks = OpenSourceMusicAPI.search_tracks(query="", limit=max(limit, 10))
        created_song_ids = []

        for track in tracks:
            external_id = str(track.get('external_id') or track.get('id') or track.get('title') or '')
            song = Song.objects.filter(source='opensource', external_id=external_id).first()

            if song is None:
                song = Song.objects.filter(
                    source='opensource',
                    title__iexact=track.get('title', ''),
                    artist__iexact=track.get('artist', ''),
                ).first()

            if song is None:
                song = Song.objects.create(
                    title=track.get('title') or 'Unknown Title',
                    artist=track.get('artist') or 'Unknown Artist',
                    genre_name=track.get('genre') or '',
                    audio_url=track.get('audio_url') or '',
                    cover_image_url=track.get('cover_image') or '',
                    duration=track.get('duration') or None,
                    external_id=external_id,
                    source='opensource',
                )

            created_song_ids.append(song.id)

        if not created_song_ids:
            return Song.objects.none()

        order = Case(
            *[When(id=song_id, then=position) for position, song_id in enumerate(created_song_ids)],
            output_field=IntegerField(),
        )
        return Song.objects.filter(id__in=created_song_ids).order_by(order)


class RecommendationScorer:
    """
    Helper class for scoring and ranking recommendations
    """
    
    @staticmethod
    def score_by_popularity(songs):
        """Score songs by how many playlists they appear in"""
        return songs.annotate(
            popularity_score=Count('playlists')
        ).order_by('-popularity_score')
    
    @staticmethod
    def score_by_recency(songs):
        """Score songs by how recently they were added"""
        return songs.order_by('-created_at')
    
    @staticmethod
    def score_by_genre_diversity(songs, target_count=10):
        """Score to maximize genre diversity in recommendations"""
        scored_songs = []
        genres_seen = Counter()
        
        # Sort by popularity first
        sorted_songs = RecommendationScorer.score_by_popularity(songs)
        
        for song in sorted_songs:
            genre_id = song.genre_id
            genre_count = genres_seen.get(genre_id, 0)
            
            # Prefer genres we haven't seen much
            diversity_score = 1.0 / (genre_count + 1)
            scored_songs.append((song, diversity_score))
            genres_seen[genre_id] += 1
        
        # Sort by diversity score
        scored_songs.sort(key=lambda x: x[1], reverse=True)
        return [song for song, score in scored_songs[:target_count]]
