from django.db import models
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
# Create your models here.

class Genre(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Subscription(models.Model):
    """User subscription model for premium features"""
    TIER_CHOICES = [
        ('free', 'Free'),
        ('premium', 'Premium'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='free')
    is_active = models.BooleanField(default=True)
    subscription_date = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.tier}"
    
    def is_premium(self):
        """Check if user has active premium subscription"""
        if self.tier == 'premium' and self.is_active:
            if self.expiry_date is None or self.expiry_date > timezone.now():
                return True
        return False
    
    def get_playlist_song_limit(self):
        """Get maximum songs allowed in a playlist"""
        return float('inf') if self.is_premium() else 5
    
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
        self.save()
    
class Song(models.Model):
    # Song source types
    SOURCE_CHOICES = [
        ('local', 'Local Upload'),
        ('jamendo', 'Jamendo'),
        ('itunes', 'iTunes'),
        ('opensource', 'Open Source Music'),
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

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']
