# Music Recommendation System Documentation

## Overview

The Music Recommendation System implements three powerful algorithms to provide personalized song recommendations to users:

1. **Collaborative Filtering** - Recommendations based on similar users
2. **Content-Based Filtering** - Recommendations based on song features
3. **Hybrid Recommendation System** - Combines both approaches

---

## 1. Collaborative Filtering

### How It Works
Analyzes users with similar music tastes and recommends songs they've added to their playlists.

### Algorithm Logic
- Finds users who have similar songs or genres in playlists
- Measures similarity by counting shared songs
- Recommends songs that similar users added but current user hasn't

### Key Methods

#### `get_similar_users(user, limit=5)`
Finds users with similar taste based on shared songs and genres.

```python
from finder.recommendations import CollaborativeFiltering

similar_users = CollaborativeFiltering.get_similar_users(request.user, limit=5)
```

**Returns:** QuerySet of User objects ordered by similarity score

#### `recommend_for_user(user, limit=10)`
Returns songs recommended by similar users.

```python
recommended_songs = CollaborativeFiltering.recommend_for_user(request.user, limit=15)
```

**Returns:** QuerySet of Song objects

### Use Cases
- Better recommendations as user base grows
- Discovers songs from niche communities
- Handles cold-start problem once user has some activity

---

## 2. Content-Based Filtering

### How It Works
Analyzes the genres and artists in user's playlists and recommends similar songs.

### Algorithm Logic
- Extracts features from user's playlist songs (genre, artist)
- Compares candidate songs with user's songs
- Scores based on feature similarity (60% genre, 40% artist)
- Returns highest-scoring songs

### Key Methods

#### `get_song_features(song)`
Extracts comparable features from a song.

```python
features = ContentBasedFiltering.get_song_features(song)
# Returns: {'genre': 1, 'artist': 'artist name', 'title': 'song title'}
```

#### `calculate_similarity(song1, song2)`
Calculates similarity between two songs (0-1 scale).

```python
similarity_score = ContentBasedFiltering.calculate_similarity(song1, song2)
# Returns: 0.6 (for example)
```

#### `recommend_for_user(user, limit=10)`
Returns songs similar to what user already likes.

```python
recommended_songs = ContentBasedFiltering.recommend_for_user(request.user, limit=15)
```

**Returns:** QuerySet of Song objects

### Use Cases
- Works immediately with new users (no cold-start problem)
- Keeps recommendations relevant to explicit user preferences
- Transparent - easy to explain why a song was recommended

---

## 3. Hybrid Recommendation System

### How It Works
Intelligently combines collaborative and content-based filtering for balanced recommendations.

### Algorithm Logic
- Gets recommendations from both algorithms
- Scores each song based on:
  - Ranking in collaborative filtering results
  - Ranking in content-based results
- Applies user-configurable weights to each algorithm
- Returns combined recommendations sorted by hybrid score

### Default Weights
- Collaborative Filtering: 50%
- Content-Based Filtering: 50%

### Key Methods

#### `recommend_for_user(user, limit=10, collaborative_weight=None, content_weight=None)`
Returns hybrid recommendations with specified weights.

```python
recommended_songs = HybridRecommendation.recommend_for_user(
    request.user,
    limit=15,
    collaborative_weight=0.5,
    content_weight=0.5
)
```

**Parameters:**
- `user`: Django User object
- `limit`: Number of recommendations (default: 10)
- `collaborative_weight`: Weight for CF (0-1)
- `content_weight`: Weight for CB (0-1)

**Returns:** List of Song objects

#### `recommend_with_custom_weights(user, collaborative_weight=0.6, content_weight=0.4, limit=10)`
Convenience method for custom weight combinations.

```python
# Favor collaborative filtering (60%) over content (40%)
recommendations = HybridRecommendation.recommend_with_custom_weights(
    request.user,
    collaborative_weight=0.6,
    content_weight=0.4,
    limit=15
)
```

#### `get_personalized_recommendations(user, method='hybrid', limit=10, **kwargs)`
Universal method for getting recommendations with any algorithm.

```python
# Get hybrid recommendations
songs = HybridRecommendation.get_personalized_recommendations(
    request.user,
    method='hybrid',
    limit=15
)

# Or get collaborative recommendations
songs = HybridRecommendation.get_personalized_recommendations(
    request.user,
    method='collaborative',
    limit=15
)

# Or get content-based recommendations
songs = HybridRecommendation.get_personalized_recommendations(
    request.user,
    method='content',
    limit=15
)
```

### Use Cases
- Best overall approach - combines strengths of both methods
- Avoids weaknesses of individual algorithms
- A/B testing different weight combinations
- Allows fine-tuning based on user feedback

---

## 4. Helper Utilities

### RecommendationScorer

Utility class for additional scoring and ranking.

#### `score_by_popularity(songs)`
Ranks songs by how many playlists they appear in.

```python
popular_songs = RecommendationScorer.score_by_popularity(Song.objects.all())
```

#### `score_by_recency(songs)`
Ranks songs by how recently they were added.

```python
recent_songs = RecommendationScorer.score_by_recency(Song.objects.all())
```

#### `score_by_genre_diversity(songs, target_count=10)`
Selects songs while maximizing genre variety.

```python
diverse_songs = RecommendationScorer.score_by_genre_diversity(
    Song.objects.all(),
    target_count=15
)
```

---

## Views and Routes

### 1. Collaborative Filtering View
**URL:** `/recommendations/collaborative/`
**Route Name:** `collab_recommendations`

Shows recommendations based on similar users.

```html
<a href="{% url 'collab_recommendations' %}">Get Collaborative Recommendations</a>
```

### 2. Content-Based Filtering View
**URL:** `/recommendations/content/`
**Route Name:** `content_recommendations`

Shows recommendations based on song features.

```html
<a href="{% url 'content_recommendations' %}">Get Content-Based Recommendations</a>
```

### 3. Hybrid Recommendation View
**URL:** `/recommendations/hybrid/`
**Route Name:** `hybrid_recommendations`

Shows hybrid recommendations with customizable weights.

```html
<!-- Default weights (50/50) -->
<a href="{% url 'hybrid_recommendations' %}">Get Hybrid Recommendations</a>

<!-- Custom weights via query parameters -->
<a href="{% url 'hybrid_recommendations' %}?collab_weight=0.6&content_weight=0.4">
    Get Recommendations (60% Collab, 40% Content)
</a>
```

### 4. API Endpoint
**URL:** `/api/recommendations/`
**Route Name:** `recommendations_api`
**Method:** GET
**Response:** JSON

Returns recommendations as JSON for AJAX/API usage.

**Query Parameters:**
- `method`: `'collaborative'`, `'content'`, or `'hybrid'` (default: 'hybrid')
- `limit`: Number of recommendations (default: 10)
- `collab_weight`: For hybrid (default: 0.5)
- `content_weight`: For hybrid (default: 0.5)

**Example Requests:**

```javascript
// Get 20 collaborative filtering recommendations
fetch('/api/recommendations/?method=collaborative&limit=20')
  .then(response => response.json())
  .then(data => console.log(data.songs));

// Get 15 hybrid recommendations with custom weights
fetch('/api/recommendations/?method=hybrid&limit=15&collab_weight=0.6&content_weight=0.4')
  .then(response => response.json())
  .then(data => console.log(data.songs));

// Get 10 content-based recommendations
fetch('/api/recommendations/?method=content&limit=10')
  .then(response => response.json())
  .then(data => console.log(data.songs));
```

**Response Format:**

```json
{
  "status": "success",
  "method": "hybrid",
  "count": 15,
  "songs": [
    {
      "id": 1,
      "title": "Song Name",
      "artist": "Artist Name",
      "genre": "Pop",
      "audio_url": "https://...",
      "cover_image": "https://...",
      "source": "local"
    },
    ...
  ]
}
```

---

## JavaScript Integration

Add recommendations to your frontend with JavaScript:

```javascript
// Fetch collaborative recommendations
async function getCollaborativeRecommendations() {
  const response = await fetch('/api/recommendations/?method=collaborative&limit=15');
  const data = await response.json();
  
  if (data.status === 'success') {
    displaySongs(data.songs);
  }
}

// Fetch hybrid recommendations with custom weights
async function getHybridRecommendations(collaborativeWeight, contentWeight) {
  const url = `/api/recommendations/?method=hybrid&limit=15&collab_weight=${collaborativeWeight}&content_weight=${contentWeight}`;
  const response = await fetch(url);
  const data = await response.json();
  
  if (data.status === 'success') {
    displaySongs(data.songs);
  }
}

function displaySongs(songs) {
  // Display songs in your UI
  songs.forEach(song => {
    console.log(`${song.title} by ${song.artist}`);
  });
}
```

---

## Best Practices

### 1. Choose the Right Algorithm

| Algorithm | Best For | Pros | Cons |
|-----------|----------|------|------|
| **Collaborative** | Mature apps with users | Discovers niche music | Slow start problem |
| **Content-Based** | All stages | Works immediately | May be repetitive |
| **Hybrid** | Production apps | Best overall balance | More complex |

### 2. Handle Cold-Start Problem
For new users with no playlists:

```python
# In recommendations.py, ContentBasedFiltering.recommend_for_user checks for this:
if not user_songs.exists():
    return ContentBasedFiltering.recommend_by_preferred_genres(user, limit)
```

### 3. Monitor Performance
Track which algorithm performs best for your users:

```python
# You can create a UserRecommendationLog model to track:
# - Which algorithm was used
# - Which songs were clicked/added to playlists
# - Engagement metrics
```

### 4. Optimize Database Queries
All methods use Django ORM efficiently:
- Uses `filter()` and `exclude()` for database-level operations
- Limits results early to reduce memory usage
- Uses `distinct()` to avoid duplicates

### 5. Fine-Tune Weights
Test different weight combinations for your user base:

```python
# A/B test different approaches
hybrid_60_40 = HybridRecommendation.recommend_with_custom_weights(user, 0.6, 0.4)
hybrid_50_50 = HybridRecommendation.recommend_with_custom_weights(user, 0.5, 0.5)
hybrid_40_60 = HybridRecommendation.recommend_with_custom_weights(user, 0.4, 0.6)
```

---

## Troubleshooting

### "No recommendations available"
- **Cause:** User has no playlists with songs
- **Solution:** Add more songs to playlists or use content-based filtering

### Recommendations too repetitive
- **Cause:** Content-based filtering relies on current preferences
- **Solution:** Use hybrid with higher collaborative weight: `collab_weight=0.6`

### Recommendations too random
- **Cause:** Collaborative filtering finding dissimilar users
- **Solution:** Use hybrid with higher content weight: `content_weight=0.6`

### Slow queries
- **Cause:** Large number of users/songs
- **Solution:** Add database indexes or implement caching

```python
# Add to model Meta:
class Song(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['genre', 'created_at']),
            models.Index(fields=['artist', 'genre']),
        ]
```

---

## Advanced Usage

### Caching Recommendations

```python
from django.core.cache import cache

def get_cached_recommendations(user_id, method='hybrid', timeout=3600):
    cache_key = f'recommendations_{user_id}_{method}'
    
    recommendations = cache.get(cache_key)
    if recommendations is None:
        user = User.objects.get(id=user_id)
        recommendations = HybridRecommendation.get_personalized_recommendations(
            user,
            method=method,
            limit=15
        )
        cache.set(cache_key, recommendations, timeout)
    
    return recommendations
```

### Batch Processing

```python
def update_all_user_recommendations():
    """Periodically update recommendations for all users"""
    for user in User.objects.all():
        recommendations = HybridRecommendation.recommend_for_user(user, limit=10)
        # Save to cache or database for quick access
```

---

## Summary

The three-algorithm system provides:
- **Flexibility** - Choose the algorithm that works best
- **Scalability** - Works with any size user base
- **Customization** - Adjust weights and parameters
- **Transparency** - Understand why recommendations are made

Start with **Hybrid** for best results, then experiment with weights based on user feedback!
