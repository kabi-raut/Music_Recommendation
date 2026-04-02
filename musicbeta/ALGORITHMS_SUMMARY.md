# Three Recommendation Algorithms - Quick Reference

## ✅ Implementation Complete

Your music app now has three powerful recommendation algorithms integrated!

---

## 📍 File Locations

| File | Purpose |
|------|---------|
| `finder/recommendations.py` | Core algorithm implementations (412 lines) |
| `finder/views.py` | View functions for recommendations |
| `finder/urls.py` | URL routes for recommendation pages |
| `finder/templates/main/recommendations.html` | Template for recommendation display |
| `finder/RECOMMENDATION_GUIDE.md` | Detailed documentation |

---

## 🎯 Algorithm 1: Collaborative Filtering

**How it works:** Finds users with similar taste and recommends what they liked

```python
from finder.recommendations import CollaborativeFiltering

# Get similar users
similar_users = CollaborativeFiltering.get_similar_users(user, limit=5)

# Get recommendations
songs = CollaborativeFiltering.recommend_for_user(user, limit=10)
```

**Access in app:**
- URL: `/recommendations/collaborative/`
- Route name: `collab_recommendations`

**Best for:**
- Mature apps with many users
- Discovering new music from communities with similar taste
- After user has added several playlists

---

## 🎯 Algorithm 2: Content-Based Filtering

**How it works:** Analyzes genres and artists user likes, recommends similar songs

```python
from finder.recommendations import ContentBasedFiltering

# Get song features
features = ContentBasedFiltering.get_song_features(song)

# Calculate similarity between songs
similarity = ContentBasedFiltering.calculate_similarity(song1, song2)

# Get recommendations
songs = ContentBasedFiltering.recommend_for_user(user, limit=10)
```

**Access in app:**
- URL: `/recommendations/content/`
- Route name: `content_recommendations`

**Best for:**
- New users (no cold-start problem)
- When you want predictable recommendations
- Transparent recommendations (easy to explain)

---

## 🎯 Algorithm 3: Hybrid Recommendation System

**How it works:** Combines both algorithms with adjustable weights (default 50/50)

```python
from finder.recommendations import HybridRecommendation

# Default weights (50% collaborative, 50% content-based)
songs = HybridRecommendation.recommend_for_user(user, limit=10)

# Custom weights
songs = HybridRecommendation.recommend_for_user(
    user,
    limit=10,
    collaborative_weight=0.6,  # 60%
    content_weight=0.4         # 40%
)

# Or use convenience method
songs = HybridRecommendation.recommend_with_custom_weights(
    user,
    collaborative_weight=0.6,
    content_weight=0.4,
    limit=10
)
```

**Access in app:**
- URL: `/recommendations/hybrid/`
- Route name: `hybrid_recommendations`
- API: `/api/recommendations/?method=hybrid&limit=15`

**Best for:**
- Production apps (best of both worlds)
- A/B testing different weight combinations
- Most users (balanced approach)

---

## 🌐 Views Available

### 1. Collaborative Filtering View
```
GET /recommendations/collaborative/
```
Shows recommendations based on similar users

### 2. Content-Based Filtering View
```
GET /recommendations/content/
```
Shows recommendations based on song features

### 3. Hybrid Recommendation View
```
GET /recommendations/hybrid/
GET /recommendations/hybrid/?collab_weight=0.6&content_weight=0.4
```
Shows hybrid recommendations with optional custom weights

### 4. API Endpoint
```
GET /api/recommendations/
Query params:
  - method: 'collaborative' | 'content' | 'hybrid' (default: 'hybrid')
  - limit: number (default: 10)
  - collab_weight: 0-1 (for hybrid, default: 0.5)
  - content_weight: 0-1 (for hybrid, default: 0.5)
```

Returns JSON with recommended songs

---

## 📱 Frontend Access

All three algorithms are accessible from the Dashboard:

```html
<!-- In your dashboard, users will see three buttons: -->
<a href="{% url 'collab_recommendations' %}" class="btn">
    👥 Collaborative Filtering
</a>
<a href="{% url 'content_recommendations' %}" class="btn">
    🏷️ Content-Based
</a>
<a href="{% url 'hybrid_recommendations' %}" class="btn">
    🔗 Hybrid System
</a>
```

---

## 💻 JavaScript API Integration

```javascript
// Get recommendations via API
async function getRecommendations(method = 'hybrid', limit = 15) {
  const params = new URLSearchParams({
    method: method,
    limit: limit
  });
  
  const response = await fetch(`/api/recommendations/?${params}`);
  const data = await response.json();
  
  if (data.status === 'success') {
    console.log(`Got ${data.count} ${method} recommendations`);
    data.songs.forEach(song => {
      console.log(`${song.title} by ${song.artist}`);
    });
  }
}

// Try different algorithms
getRecommendations('collaborative', 10);
getRecommendations('content', 10);
getRecommendations('hybrid', 15);

// Custom hybrid weights
async function getCustomHybrid(collaborativeWeight, contentWeight) {
  const params = new URLSearchParams({
    method: 'hybrid',
    limit: 15,
    collab_weight: collaborativeWeight,
    content_weight: contentWeight
  });
  
  const response = await fetch(`/api/recommendations/?${params}`);
  const data = await response.json();
  return data.songs;
}

// Example: 60% collaborative, 40% content-based
const songs = await getCustomHybrid(0.6, 0.4);
```

---

## 🔧 Database Models Used

The algorithms work with your existing models:

```python
# Models from finder/models.py
User          # Django built-in
Playlist      # User's music collections
Song          # Music tracks with genre, artist, etc.
Genre         # Song categories
UserPreference # User's liked genres (optional)
```

---

## 🚀 How to Use in Your Code

### Backend Usage

```python
from finder.recommendations import (
    CollaborativeFiltering,
    ContentBasedFiltering,
    HybridRecommendation
)

@login_required
def my_custom_view(request):
    # Get recommendations
    songs = HybridRecommendation.recommend_for_user(
        request.user,
        limit=20
    )
    
    return render(request, 'template.html', {
        'recommendations': songs
    })
```

### Frontend Template Usage

```django
{% for song in recommendations %}
  <div class="song-card">
    <h5>{{ song.title }}</h5>
    <p>{{ song.artist }}</p>
    <a href="{% url 'add_song_to_playlist' playlist.id song.id %}">
      Add to Playlist
    </a>
  </div>
{% endfor %}
```

---

## 📊 Algorithm Comparison

| Feature | Collaborative | Content-Based | Hybrid |
|---------|---------------|---------------|--------|
| **Cold Start** | ❌ Poor | ✅ Excellent | ✅ Good |
| **Scalability** | ✅ Good | ✅ Good | ✅ Good |
| **Diversity** | ✅ Good | ❌ Limited | ✅ Good |
| **Serendipity** | ✅ High | ❌ Low | ✅ Medium |
| **Explainability** | ❌ Hard | ✅ Easy | ⚠️ Medium |
| **Simplicity** | ❌ Complex | ✅ Simple | ⚠️ Medium |

---

## ⚙️ Configuration & Tuning

### Adjust Hybrid Weights

```python
# In your app, favor collaborative more
recommendations = HybridRecommendation.recommend_for_user(
    user,
    collaborative_weight=0.7,  # 70% collaborative
    content_weight=0.3         # 30% content
)

# Or favor content-based more
recommendations = HybridRecommendation.recommend_for_user(
    user,
    collaborative_weight=0.3,  # 30% collaborative
    content_weight=0.7         # 70% content
)
```

### Content-Based Similarity Weights

Currently configured as:
- Genre match: 60%
- Artist match: 40%

To modify, edit `ContentBasedFiltering.calculate_similarity()`:

```python
# Make genre more important
similarity += 0.7  # genre weight
similarity += 0.3  # artist weight

# Or make artist more important
similarity += 0.5  # genre weight
similarity += 0.5  # artist weight
```

---

## 🎓 Learning Resources

- Full documentation: `finder/RECOMMENDATION_GUIDE.md`
- Algorithm code: `finder/recommendations.py`
- Views: `finder/views.py` (lines with @login_required decorators)
- Template: `finder/templates/main/recommendations.html`

---

## ✨ Features

- ✅ Three distinct algorithms
- ✅ Configurable weights for hybrid approach
- ✅ JSON API endpoint for frontend integration
- ✅ Template with beautiful UI for each algorithm
- ✅ Similar users display (collaborative)
- ✅ Genre diversity scoring helper
- ✅ Popularity and recency scoring
- ✅ Full documentation and examples
- ✅ Works with existing database
- ✅ No additional dependencies needed

---

## 🐛 Testing the Algorithms

1. **Create test data:**
   - Add songs to database
   - Create playlists with different songs
   - As different users

2. **Test collaborative filtering:**
   - Visit `/recommendations/collaborative/`
   - See similar users recommendations

3. **Test content-based:**
   - Visit `/recommendations/content/`
   - See genre/artist based recommendations

4. **Test hybrid:**
   - Visit `/recommendations/hybrid/`
   - Try with different weights: `?collab_weight=0.6&content_weight=0.4`

5. **Test API:**
   ```bash
   curl "http://localhost:8000/api/recommendations/?method=hybrid&limit=10"
   ```

---

## 🚨 Troubleshooting

**No recommendations showing?**
- Make sure user has playlists with songs
- Check that other users have playlists (for collaborative filtering)

**Recommendations too similar?**
- Use hybrid with higher collaborative weight (0.6)
- Add more diversity in user playlists

**Slow performance?**
- Add database indexes for genre and artist
- Consider caching results
- Limit number of songs to compare

---

## 🎉 You're All Set!

Your recommendation system is ready to use. Start with the **Hybrid Recommendation System** for best results, then experiment with weights and algorithms based on user feedback!

**Next Steps:**
1. View recommendations at `/recommendations/hybrid/`
2. Try different algorithms and weights
3. Monitor user engagement
4. Fine-tune weights based on feedback
