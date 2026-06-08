"""
Script to create default subscription plans.
Run: python manage.py shell -c "exec(open('create_plans.py').read())"
"""

from finder.models import SubscriptionPlan

# Delete existing plans first
SubscriptionPlan.objects.all().delete()

# Create Free Plan
free_plan = SubscriptionPlan.objects.create(
    name="Free",
    tier="free",
    price=0,
    duration_days=0,  # Unlimited for free
    description="Perfect for trying out MusicBeta",
    features="Basic music discovery\nLocal library access\nBasic recommendations\nPublic playlists",
    max_playlists=3,
    max_songs_per_playlist=5,
    ad_free=False,
    download_available=False,
    offline_mode=False,
    hd_audio=False,
    is_active=True,
)
print(f"✓ Created: {free_plan}")

# Create Basic Plan
basic_plan = SubscriptionPlan.objects.create(
    name="Basic",
    tier="basic",
    price=2.99,
    duration_days=30,
    description="Great for casual listeners",
    features="Unlimited songs per playlist\nAdvanced search filters\nPersonal recommendations\nPrivate playlists\nListening history",
    max_playlists=10,
    max_songs_per_playlist=50,
    ad_free=False,
    download_available=False,
    offline_mode=False,
    hd_audio=False,
    is_active=True,
)
print(f"✓ Created: {basic_plan}")

# Create Pro Plan
pro_plan = SubscriptionPlan.objects.create(
    name="Pro",
    tier="pro",
    price=4.99,
    duration_days=30,
    description="For serious music lovers",
    features="Everything in Basic\nHD Audio Quality\nMood-based recommendations\nPlaylist sharing\nAd-free experience\nDownload for offline",
    max_playlists=50,
    max_songs_per_playlist=999,  # Effectively unlimited
    ad_free=True,
    download_available=True,
    offline_mode=True,
    hd_audio=True,
    is_active=True,
)
print(f"✓ Created: {pro_plan}")

# Create Premium Plan
premium_plan = SubscriptionPlan.objects.create(
    name="Premium",
    tier="premium",
    price=7.99,
    duration_days=30,
    description="The ultimate music experience",
    features="Everything in Pro\nAI mood detection\nReal-time recommendations\nCollaborative filtering\nPublic playlist features\nFeatured playlists\nUnlimited everything",
    max_playlists=999,  # Effectively unlimited
    max_songs_per_playlist=999,  # Effectively unlimited
    ad_free=True,
    download_available=True,
    offline_mode=True,
    hd_audio=True,
    is_active=True,
)
print(f"✓ Created: {premium_plan}")

print("\n✅ All subscription plans created successfully!")
print(f"Total plans: {SubscriptionPlan.objects.count()}")
