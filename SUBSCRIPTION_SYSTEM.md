# Subscription System Documentation

## Overview
The Music Finder application now includes a tiered subscription system with two plans: **Free** and **Premium**.

## Features Implemented

### 1. **Subscription Model**
- **Location**: `finder/models.py`
- **Model**: `Subscription`
- **Tiers**: 
  - `Free` (Default for all new users)
  - `Premium` (Paid subscription)

### 2. **Free Plan Limitations**
- **Playlist Song Limit**: 5 songs per playlist
- **Algorithms Access**: NO (disabled)
- **Dynamic Playlists**: NO

### 3. **Premium Plan Benefits**
- **Price**: $4.99/month
- **Playlist Song Limit**: Unlimited songs
- **Algorithms Access**: YES
  - Collaborative Filtering Recommendations
  - Content-Based Filtering Recommendations
  - Hybrid Recommendation System
- **Dynamic Playlists**: YES (powered by AI algorithms)

---

## Implementation Details

### User Flow

1. **New User Registration**
   - Automatically gets a FREE subscription
   - Subscription created via Django signals in `finder/signals.py`

2. **Free User Actions**
   - Can create playlists (limited to 5 songs each)
   - Can browse and discover songs
   - Cannot access algorithm-based recommendations
   - Cannot create dynamic playlists

3. **Premium User Actions**
   - Can create unlimited playlists
   - Can add unlimited songs to playlists
   - Can access all recommendation algorithms
   - Can create dynamic playlists

### Database Changes
- New migration: `finder/migrations/0006_subscription.py`
- New table: `finder_subscription`

### Views Updated

1. **`views.dashboard()`** - Enhanced with subscription info
2. **`views.playlist_detail()`** - Shows song count and limit warnings
3. **`views.add_song_to_playlist()`** - Enforces 5-song limit for free users
4. **`views.save_external_song()`** - Enforces limit for external songs
5. **`views.subscription_page()`** - NEW: Displays subscription status and upgrade options
6. **`views.subscribe_premium()`** - NEW: Upgrades user to premium
7. **`views.cancel_subscription()`** - NEW: Cancels premium subscription
8. **`views.collaborative_filtering_recommendations()`** - Requires premium
9. **`views.content_based_recommendations()`** - Requires premium
10. **`views.hybrid_recommendations()`** - Requires premium

### URL Routes Added
```python
path('subscription/', views.subscription_page, name='subscription_page'),
path('subscription/upgrade/', views.subscribe_premium, name='subscribe_premium'),
path('subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
```

### Templates Created

1. **`subscription.html`** - NEW
   - Displays current subscription status
   - Shows Free and Premium plan details
   - Upgrade and cancel buttons
   - Feature comparison

2. **`base.html`** - UPDATED
   - Added "Subscription" link in user dropdown menu

3. **`playlist_detail.html`** - UPDATED
   - Shows song count and limit for free users
   - Displays alerts about subscription status
   - Disables "Add Songs" button when limit is reached

---

## Key Functions

### Subscription Model Methods

```python
subscription.is_premium()
# Returns: bool - Whether user has active premium subscription

subscription.get_playlist_song_limit()
# Returns: int/float - Maximum songs allowed (5 or infinity)

subscription.activate_premium(duration_days=30)
# Activates premium subscription for specified days

subscription.cancel_subscription()
# Downgrade user back to free tier
```

### Usage Examples

#### Check if user is premium:
```python
subscription = Subscription.objects.get_or_create(user=user)[0]
if subscription.is_premium():
    # Show premium features
```

#### Get max songs:
```python
limit = subscription.get_playlist_song_limit()
if playlist.songs.count() >= limit:
    # User has reached limit
```

#### Upgrade user to premium:
```python
subscription = Subscription.objects.get_or_create(user=user)[0]
subscription.activate_premium(duration_days=30)
```

---

## User Experience

### Free User
1. Signs up → Auto-gets free subscription
2. Creates playlist → Can add first 5 songs
3. Tries to add 6th song → Error message: "Free users can only have 5 songs per playlist. Upgrade to Premium!"
4. Clicks "Upgrade" → Redirected to subscription page
5. Clicks "Upgrade to Premium" → Gets premium access
6. Can now add unlimited songs and use algorithms

### Premium User
1. Can create unlimited playlists with unlimited songs
2. Can access all recommendation algorithms:
   - Click "Recommendations" → View personalized suggestions
   - Choose algorithm: Collaborative, Content-Based, or Hybrid
3. Can cancel subscription anytime (back to free tier)

---

## Admin Interface

The `Subscription` model is registered in Django Admin:

**Location**: `/admin/finder/subscription/`

**Fields visible**:
- User
- Subscription Tier (Free/Premium)
- Is Active
- Subscription Date
- Expiry Date (for premium subscriptions)

**Filtering**: By tier, active status, and subscription date
**Search**: By username or email

---

## Algorithms Integration

### Collaborative Filtering
- Recommends songs based on similar users' preferences
- Shows similar users with same taste
- **Premium-only feature**

### Content-Based Filtering
- Recommends songs based on:
  - Genres in user's playlists
  - Artists in user's playlists
- **Premium-only feature**

### Hybrid Recommendation
- Combines both collaborative and content-based approaches
- Customizable weights for algorithm balance
- **Premium-only feature**

---

## Future Enhancements

1. **Payment Integration**
   - Stripe/PayPal integration
   - Actual payment processing

2. **Subscription Tiers**
   - Basic: 10 songs/playlist ($2.99)
   - Pro: Unlimited songs ($4.99)
   - Plus: Unlimited + advanced features ($7.99)

3. **Expiry Notifications**
   - Email reminders before subscription expires
   - Auto-renewal options

4. **Usage Analytics**
   - Track premium feature usage
   - Generate reports for admins

5. **Free Trial**
   - 14-day free premium trial for new users
   - Upgrade reminders

---

## Testing Checklist

- [ ] New user auto-gets free subscription
- [ ] Free user limited to 5 songs per playlist
- [ ] Free user cannot access algorithms
- [ ] Premium upgrade works
- [ ] Premium user can add unlimited songs
- [ ] Premium user can access all algorithms
- [ ] Premium cancellation works
- [ ] Subscription page displays correctly
- [ ] Admin can manage subscriptions
- [ ] Error messages display properly

---

## Troubleshooting

### User doesn't have subscription
**Solution**: Delete the user and recreate. Django signals will create subscription automatically.

### Subscription not checking
**Make sure**: `finder/apps.py` has `ready()` method that imports signals.

### Algorithms not restricted
**Check**: Each recommendation view has `subscription.is_premium()` check at the beginning.

### Migration failed
**Run**: 
```bash
python manage.py migrate finder 0006_subscription
```
