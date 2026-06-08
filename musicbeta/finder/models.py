from django.db import models
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
import uuid
# Create your models here.

class Genre(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class SubscriptionPlan(models.Model):
    """Subscription plans with pricing"""
    TIER_CHOICES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('pro', 'Pro'),
        ('premium', 'Premium'),
    ]
    
    name = models.CharField(max_length=100)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration_days = models.IntegerField(default=30, help_text="Subscription duration in days")
    description = models.TextField(blank=True)
    features = models.TextField(help_text="Features separated by newlines")
    max_playlists = models.IntegerField(default=3)
    max_songs_per_playlist = models.IntegerField(default=5)
    ad_free = models.BooleanField(default=False)
    download_available = models.BooleanField(default=False)
    offline_mode = models.BooleanField(default=False)
    hd_audio = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['price']
    
    def __str__(self):
        return f"{self.name} - ${self.price}"
    
    def get_features_list(self):
        """Return features as a list"""
        return [f.strip() for f in self.features.split('\n') if f.strip()]


class Subscription(models.Model):
    """User subscription model for premium features"""
    TIER_CHOICES = [
        ('free', 'Free'),
        ('premium', 'Premium'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='free')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='subscriptions')
    is_active = models.BooleanField(default=True)
    subscription_date = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.tier}"
    
    def is_premium(self):
        """Check if user has active premium subscription"""
        if self.is_active and self.tier == 'premium':
            if self.expiry_date is None or self.expiry_date > timezone.now():
                return True
        return False
    
    def get_playlist_song_limit(self):
        """Get maximum songs allowed in a playlist"""
        if self.is_premium():
            return 999
        return 5

    def get_playlist_limit(self):
        """Get maximum number of playlists allowed"""
        if self.is_premium():
            return 999
        return 3

    def can_download(self):
        """Whether premium users can download."""
        return self.is_premium()

    def can_use_offline_mode(self):
        """Whether premium users can access offline mode."""
        return self.is_premium()

    def can_use_hd_audio(self):
        """Whether premium users can access HD audio."""
        return self.is_premium()

    def is_ad_free(self):
        """Whether premium users have ad-free playback."""
        return self.is_premium()

    def can_use_advanced_recommendations(self):
        """Whether current subscription can access recommendation engines."""
        return self.is_premium()

    def can_share_playlists(self):
        """Whether premium users can publish playlist share links."""
        return self.is_premium()
    
    def activate_premium(self, duration_days=30):
        """Activate premium subscription"""
        self.tier = 'premium'
        self.is_active = True
        self.expiry_date = timezone.now() + timedelta(days=duration_days)
        self.save()
    
    def cancel_subscription(self):
        """Cancel premium subscription"""
        self.tier = 'free'
        self.is_active = False
        self.expiry_date = None
        self.plan = None
        self.save()
    
class Song(models.Model):
    # Song source types
    SOURCE_CHOICES = [
        ('local', 'Local Upload'),
        ('itunes', 'iTunes'),
    ]
    
    title = models.CharField(max_length=200, default='Unknown Title')
    artist = models.CharField(max_length=200, default='Unknown Artist')
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE, null=True, blank=True)
    genre_name = models.CharField(max_length=100, blank=True, null=True)  # For API songs without Genre FK
    
    # Local file fields
    audio_file = models.FileField(upload_to='songs/', blank=True, null=True)
    cover_image = models.ImageField(upload_to='covers/', blank=True, null=True)
    
    # External API fields
    audio_url = models.URLField(max_length=500, blank=True, null=True)  # For streaming from APIs
    cover_image_url = models.URLField(max_length=500, blank=True, null=True)  # External cover image
    external_id = models.CharField(max_length=100, blank=True, null=True)  # API's song ID
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='local')
    
    duration = models.IntegerField(blank=True, null=True, help_text="Duration in seconds")
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Mood and metadata
    MOOD_CHOICES = [
        ('happy', 'Happy'),
        ('sad', 'Sad'),
        ('focus', 'Focus'),
        ('energetic', 'Energetic'),
        ('calm', 'Calm'),
        ('romantic', 'Romantic'),
    ]
    mood = models.CharField(max_length=20, choices=MOOD_CHOICES, null=True, blank=True)
    play_count = models.IntegerField(default=0)
    like_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.title} by {self.artist}"
    
    def get_audio_source(self):
        """Return the audio source URL or file"""
        if self.audio_url:
            return self.audio_url
        elif self.audio_file:
            return self.audio_file.url
        return None
    
    def get_cover_image(self):
        """Return the cover image URL or file"""
        if self.cover_image_url:
            return self.cover_image_url
        elif self.cover_image:
            return self.cover_image.url
        return None
    
    def get_genre_display(self):
        """Return genre name from either FK or text field"""
        if self.genre:
            return self.genre.name
        return self.genre_name or "Unknown"
    
    class Meta:
        ordering = ['-created_at']
        unique_together = [['external_id', 'source']]  # Prevent duplicate API songs
    
class UserPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    liked_genres = models.ManyToManyField(Genre, blank=True)

    def __str__(self):
        return f"Preferences of {self.user.username}"
    
class Playlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    songs = models.ManyToManyField(Song, blank=True, related_name='playlists')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Playlist sharing and visibility
    is_public = models.BooleanField(default=False)
    share_link = models.CharField(max_length=100, unique=True, blank=True, null=True)
    is_auto_generated = models.BooleanField(default=False)
    playlist_type = models.CharField(
        max_length=20,
        choices=[('manual', 'Manual'), ('daily_mix', 'Daily Mix'), ('top_picks', 'Top Picks'), ('mood', 'Mood Based')],
        default='manual'
    )

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']
    
    def generate_share_link(self):
        """Generate a unique share link for the playlist"""
        if not self.share_link:
            self.share_link = f"pl_{self.id}_{uuid.uuid4().hex[:8]}"
            self.save()


# New Models for Enhanced Features

class SongLike(models.Model):
    """Track user likes/favorites of songs"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='liked_songs')
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='liked_by_users')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'song')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} likes {self.song.title}"


class ListeningHistory(models.Model):
    """Track user listening history for personalization"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listening_history')
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='listening_history')
    played_at = models.DateTimeField(auto_now_add=True)
    duration_played = models.IntegerField(default=0, help_text="Duration played in seconds")
    completed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-played_at']
    
    def __str__(self):
        return f"{self.user.username} played {self.song.title}"


class MoodPreference(models.Model):
    """Track user mood preferences and listening patterns"""
    MOOD_CHOICES = [
        ('happy', 'Happy'),
        ('sad', 'Sad'),
        ('focus', 'Focus'),
        ('energetic', 'Energetic'),
        ('calm', 'Calm'),
        ('romantic', 'Romantic'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mood_preferences')
    mood = models.CharField(max_length=20, choices=MOOD_CHOICES)
    preference_score = models.FloatField(default=0.0)  # 0-1 score
    last_selected = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'mood')
    
    def __str__(self):
        return f"{self.user.username} - {self.mood} ({self.preference_score})"


class FeaturedSong(models.Model):
    """Admin-featured songs for homepage banners"""
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='featured_instances')
    title = models.CharField(max_length=200, default="Featured Music")
    description = models.TextField(blank=True)
    banner_image_url = models.URLField(blank=True, null=True)
    featured_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-display_order', '-featured_at']
    
    def __str__(self):
        return f"Featured: {self.song.title}"


class ReportedContent(models.Model):
    """Track reported/flagged content for moderation"""
    CONTENT_TYPE_CHOICES = [
        ('playlist', 'Playlist'),
        ('song', 'Song'),
    ]
    
    REASON_CHOICES = [
        ('explicit', 'Explicit Content'),
        ('copyright', 'Copyright Violation'),
        ('spam', 'Spam'),
        ('inappropriate', 'Inappropriate'),
        ('other', 'Other'),
    ]
    
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_filed')
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES)
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, null=True, blank=True)
    song = models.ForeignKey(Song, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    description = models.TextField()
    reported_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-reported_at']
    
    def __str__(self):
        return f"Report on {self.content_type} by {self.reported_by.username}"


class RecommendationCache(models.Model):
    """Cache recommendations to reduce compute"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cached_recommendations')
    method = models.CharField(max_length=50, choices=[('collaborative', 'Collaborative'), ('content', 'Content-Based'), ('hybrid', 'Hybrid')])
    recommendations = models.JSONField()  # Store song IDs as JSON array
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'method')
    
    def is_valid(self):
        """Check if cache is still valid"""
        return timezone.now() < self.expires_at
    
    def __str__(self):
        return f"{self.user.username} - {self.method}"


class PaymentRecord(models.Model):
    """Track completed and failed subscription payments."""
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='NPR')
    provider = models.CharField(max_length=30, default='khalti')
    provider_reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    raw_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        plan_name = self.plan.name if self.plan else 'Unknown plan'
        return f"{self.user.username} paid {self.amount} {self.currency} ({plan_name})"


class SubscriptionChangeLog(models.Model):
    """Audit trail for subscription tier/plan changes."""
    SOURCE_CHOICES = [
        ('user_purchase', 'User Purchase'),
        ('user_cancel', 'User Cancel'),
        ('admin_update', 'Admin Update'),
        ('system', 'System'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscription_change_logs')
    previous_tier = models.CharField(max_length=20, blank=True)
    new_tier = models.CharField(max_length=20)
    previous_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='previous_plan_changes',
    )
    new_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='new_plan_changes',
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscription_changes_made',
    )
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default='system')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}: {self.previous_tier or 'unknown'} -> {self.new_tier}"


class AdminActionLog(models.Model):
    """General audit trail for custom admin portal actions."""
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_actions')
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=50, blank=True)
    target_label = models.CharField(max_length=255, blank=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        actor_name = self.actor.username if self.actor else 'system'
        return f"{actor_name}: {self.action}"


class RecommendationOverride(models.Model):
    """Manual admin overrides for recommendation feeds."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recommendation_overrides', null=True, blank=True)
    recommended_song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='manual_recommendations')
    reason = models.CharField(max_length=255, default='Admin curated recommendation')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.user:
            return f"Override: {self.recommended_song.title} for {self.user.username}"
        return f"Global override: {self.recommended_song.title}"


class SearchHistory(models.Model):
    """Track user search queries for analytics and personalization"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='search_history')
    query = models.CharField(max_length=255)
    source_filter = models.CharField(max_length=20, blank=True, default='')
    genre_filter = models.CharField(max_length=100, blank=True, default='')
    searched_at = models.DateTimeField(auto_now_add=True)
    results_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-searched_at']
        indexes = [
            models.Index(fields=['user', '-searched_at']),
            models.Index(fields=['query', '-searched_at']),
        ]

    def __str__(self):
        return f"{self.user.username} searched '{self.query}'"
