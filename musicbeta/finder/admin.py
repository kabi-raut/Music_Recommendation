from django.contrib import admin
from .models import Genre, Song, UserPreference, Playlist, Subscription

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    ordering = ('name',)

@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'artist', 'genre', 'audio_file')
    list_filter = ('genre', 'artist')
    search_fields = ('title', 'artist', 'genre__name')
    ordering = ('-id',)

@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'user')
    filter_horizontal = ('liked_genres',)

@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('name', 'user__username')
    ordering = ('-created_at',)

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'tier', 'is_active', 'subscription_date', 'expiry_date')
    list_filter = ('tier', 'is_active', 'subscription_date')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('subscription_date',)
    ordering = ('-subscription_date',)


