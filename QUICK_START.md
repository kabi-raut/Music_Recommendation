# Recommendation Algorithms - Quick Start Guide

## 🚀 What You Just Got

Three fully integrated recommendation algorithms for your music discovery app:

1. **Collaborative Filtering** - What similar users like
2. **Content-Based Filtering** - What matches your taste
3. **Hybrid System** - The best of both worlds

---

## 📍 Access Your Recommendations

### From Dashboard
Users can now see three "Smart Recommendations" buttons:
- 👥 **Collaborative Filtering** - Based on similar users
- 🏷️ **Content-Based** - Based on genres/artists
- 🔗 **Hybrid System** - Combined approach

### From URL
```
/recommendations/collaborative/
/recommendations/content/
/recommendations/hybrid/
```

### From API
```
GET /api/recommendations/?method=hybrid&limit=15
```

---

## ⚡ Quick Code Usage

### In Your Views

```python
from finder.recommendations import HybridRecommendation

@login_required
def my_view(request):
    # Get 10 hybrid recommendations
    songs = HybridRecommendation.recommend_for_user(request.user, limit=10)
    return render(request, 'template.html', {'songs': songs})
```

### In Your Templates

```django
{% for song in songs %}
  <div>
    <h5>{{ song.title }}</h5>
    <p>{{ song.artist }}</p>
    <audio controls>
      <source src="{{ song.get_audio_source }}" type="audio/mpeg">
    </audio>
  </div>
{% endfor %}
```

### In JavaScript

```javascript
// Get hybrid recommendations
const response = await fetch('/api/recommendations/?method=hybrid&limit=15');
const data = await response.json();

data.songs.forEach(song => {
  console.log(`${song.title} by ${song.artist}`);
});
```

---

## 🎯 Choosing an Algorithm

| Situation | Use |
|-----------|-----|
| New user with no playlists | **Content-Based** |
| User has several playlists | **Hybrid** |
| App has many users | **Collaborative** |
| Want balanced approach | **Hybrid** (default) |
| Want easy to explain | **Content-Based** |

---

## 🔧 Customizing Hybrid Weights

### Default (50/50)
```python
songs = HybridRecommendation.recommend_for_user(user, limit=10)
```

### Via URL Parameter
```
/recommendations/hybrid/?collab_weight=0.6&content_weight=0.4
```

### In Python Code
```python
songs = HybridRecommendation.recommend_for_user(
    user,
    limit=10,
    collaborative_weight=0.6,  # 60%
    content_weight=0.4         # 40%
)
```

---

## 📚 Full Documentation

For detailed information:
- **Algorithm Details:** `finder/RECOMMENDATION_GUIDE.md`
- **Summary:** `ALGORITHMS_SUMMARY.md`
- **Code Examples:** `finder/examples.py`
- **Source Code:** `finder/recommendations.py`

---

## 🧪 Testing

### 1. Create Test Data
- Add some songs to your database
- Create a couple playlists with different songs
- Do this as different users

### 2. Visit Recommendation Pages
```
http://localhost:8000/recommendations/hybrid/
http://localhost:8000/recommendations/collaborative/
http://localhost:8000/recommendations/content/
```

### 3. Test the API
```bash
curl "http://localhost:8000/api/recommendations/?method=hybrid&limit=10"
```

### 4. Try Different Weights
```
http://localhost:8000/recommendations/hybrid/?collab_weight=0.7&content_weight=0.3
```

---

## 📊 Files Added/Modified

### New Files
- `finder/recommendations.py` - Core algorithms (412 lines)
- `finder/templates/main/recommendations.html` - UI template
- `finder/examples.py` - Usage examples
- `finder/RECOMMENDATION_GUIDE.md` - Full documentation
- `ALGORITHMS_SUMMARY.md` - Quick reference

### Modified Files
- `finder/views.py` - Added 5 new views for recommendations
- `finder/urls.py` - Added 4 new URL routes
- `finder/templates/main/dashboard.html` - Added recommendation buttons

---

## 💡 Key Features

✅ **Three Algorithms**
- Collaborative Filtering
- Content-Based Filtering
- Hybrid (configurable weights)

✅ **Multiple Access Methods**
- Web UI with beautiful templates
- JSON API endpoint
- Python functions for backend use

✅ **Smart Handling**
- Prevents recommending songs user already has
- Handles new users automatically
- Finds similar users for collaboration

✅ **Helper Utilities**
- Score by popularity
- Score by recency
- Score by genre diversity

✅ **Production Ready**
- No additional dependencies
- Works with existing models
- Database efficient
- Cacheable results

---

## 🔥 What Makes It Work

The algorithms use your existing data:
```
User → Playlists → Songs → Genre, Artist
```

- **Collaborative:** "Who else liked these songs?"
- **Content-Based:** "What songs are similar to these?"
- **Hybrid:** "Both approaches, balanced together"

---

## 🎓 Learning Path

1. **Start Here:** Visit `/recommendations/hybrid/`
2. **Try Others:** Visit `/recommendations/collaborative/` and `/content/`
3. **Compare Results:** Note differences in recommendations
4. **Adjust Weights:** Test different hybrid weights
5. **Use API:** Integrate into custom features
6. **Optimize:** Cache results, monitor usage

---

## ⚙️ Next Steps

1. **Deploy:** Your algorithms are ready to use
2. **Monitor:** Track which algorithm users prefer
3. **Optimize:** Adjust weights based on engagement
4. **Extend:** Add more features using recommendations
5. **Share:** Tell users about recommendations in UI

---

## 🐛 Common Issues & Solutions

**Q: No recommendations showing?**
A: Make sure user has playlists with songs added

**Q: Recommendations too repetitive?**
A: Increase collaborative weight: `collab_weight=0.6`

**Q: Recommendations too random?**
A: Increase content weight: `content_weight=0.6`

**Q: Need to show similar users?**
A: Use collaborative filtering - it includes similar users list

---

## 📞 Support

For detailed help:
- Read `finder/RECOMMENDATION_GUIDE.md` for algorithm details
- Check `finder/examples.py` for code samples
- Review `finder/recommendations.py` for implementation

---

## 🎉 You're All Set!

Your music recommendation system is live and ready!

**Next:** Try visiting `/recommendations/hybrid/` and see personalized recommendations in action!
