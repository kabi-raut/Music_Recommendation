from django.contrib import admin
from .models import (
    Genre, Song, UserPreference, Playlist, Subscription, SubscriptionPlan,
    SongLike, ListeningHistory, MoodPreference, FeaturedSong,
    ReportedContent, RecommendationCache, PaymentRecord, RecommendationOverride,
    SubscriptionChangeLog, SearchHistory
)

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    ordering = ('name',)

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'tier', 'price', 'duration_days', 'is_active')
    list_filter = ('tier', 'is_active', 'ad_free', 'hd_audio')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)
    ordering = ('price',)

@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'artist', 'genre', 'mood', 'play_count', 'like_count')
    list_filter = ('genre', 'artist', 'mood', 'source')
    search_fields = ('title', 'artist', 'genre__name')
    ordering = ('-id',)
    readonly_fields = ('play_count', 'like_count')

@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'user')
    filter_horizontal = ('liked_genres',)

@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'is_public', 'playlist_type', 'created_at')
    list_filter = ('created_at', 'user', 'is_public', 'playlist_type')
    search_fields = ('name', 'user__username')
    ordering = ('-created_at',)

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'tier', 'plan', 'is_active', 'subscription_date', 'expiry_date')
    list_filter = ('tier', 'is_active', 'subscription_date', 'plan')
    search_fields = ('user__username', 'user__email', 'plan__name')
    readonly_fields = ('subscription_date',)
    ordering = ('-subscription_date',)

@admin.register(SongLike)
class SongLikeAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'song', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('user__username', 'song__title')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

@admin.register(ListeningHistory)
class ListeningHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'song', 'played_at', 'duration_played', 'completed')
    list_filter = ('played_at', 'user', 'completed')
    search_fields = ('user__username', 'song__title')
    ordering = ('-played_at',)
    readonly_fields = ('played_at',)

@admin.register(MoodPreference)
class MoodPreferenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'mood', 'preference_score', 'last_selected')
    list_filter = ('mood', 'last_selected')
    search_fields = ('user__username',)
    ordering = ('-preference_score',)

@admin.register(FeaturedSong)
class FeaturedSongAdmin(admin.ModelAdmin):
    list_display = ('id', 'song', 'title', 'is_active', 'display_order', 'featured_at', 'expires_at')
    list_filter = ('is_active', 'featured_at')
    search_fields = ('song__title', 'title')
    ordering = ('-display_order', '-featured_at')

@admin.register(ReportedContent)
class ReportedContentAdmin(admin.ModelAdmin):
    list_display = ('id', 'reported_by', 'content_type', 'reason', 'is_resolved', 'reported_at')
    list_filter = ('reason', 'is_resolved', 'reported_at', 'content_type')
    search_fields = ('reported_by__username', 'description')
    ordering = ('-reported_at',)

@admin.register(RecommendationCache)
class RecommendationCacheAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'method', 'created_at', 'expires_at')
    list_filter = ('method', 'created_at')
    search_fields = ('user__username',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'plan', 'amount', 'currency', 'provider', 'status', 'created_at')
    list_filter = ('status', 'provider', 'currency', 'created_at')
    search_fields = ('user__username', 'provider_reference', 'notes')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)


@admin.register(RecommendationOverride)
class RecommendationOverrideAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'recommended_song', 'reason', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__username', 'recommended_song__title', 'reason')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)


@admin.register(SubscriptionChangeLog)
class SubscriptionChangeLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'previous_tier', 'new_tier', 'previous_plan', 'new_plan', 'source', 'created_at')
    list_filter = ('source', 'new_tier', 'created_at')
    search_fields = ('user__username', 'notes', 'previous_tier', 'new_tier')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'query', 'source_filter', 'genre_filter', 'results_count', 'searched_at')
    list_filter = ('source_filter', 'genre_filter', 'searched_at')
    search_fields = ('user__username', 'query')
    ordering = ('-searched_at',)
    readonly_fields = ('searched_at',)


