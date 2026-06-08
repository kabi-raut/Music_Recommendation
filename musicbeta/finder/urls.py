from django.urls import path
from . import views
from .admin_ops_views import admin_portal
from . import api_views
from django.contrib.auth.views import LogoutView
from django.contrib.auth.decorators import login_required
# reverse_lazy not required here

urlpatterns = [
    path('', views.home, name='home'),
    path('home/', views.home, name='home'),
    path('login/', views.unified_login, name='login'),
    path('forgot-password/', views.forgot_password_request, name='forgot_password'),
    path('forgot-password/verify-otp/', views.verify_password_otp, name='verify_password_otp'),
    path('forgot-password/resend-otp/', views.resend_password_otp, name='resend_password_otp'),
    path('forgot-password/reset/', views.reset_password_otp, name='reset_password_otp'),
    path('sign-up', views.sign_up, name='sign_up'),
    path('ops-admin/', admin_portal, name='admin_portal'),
    # logout route: logs the user out and renders a logged-out page
    path('logout/', LogoutView.as_view(template_name='registration/logged_out.html'), name='logout'),
    
    # Songs routes
    path('songs/', views.songs_list, name='songs_list'),
    
    # Dynamic music discovery routes
    path('discover/', views.discover_music, name='discover_music'),
    path('discover/<str:source>/', views.browse_by_source, name='browse_by_source'),
    path('save-external-song/', views.save_external_song, name='save_external_song'),
    
    # Dashboard and Playlist routes
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path("playlist/create/", views.create_playlist, name="create_playlist"),
    path("playlist/<int:playlist_id>/", views.playlist_detail, name="playlist_detail"),
    path("playlist/share/<str:share_link>/", views.public_playlist_view, name="public_playlist_view"),
    path("playlist/<int:playlist_id>/edit/", views.edit_playlist, name="edit_playlist"),
    path("playlist/<int:playlist_id>/delete/", views.delete_playlist, name="delete_playlist"),
    
    # Add/Remove songs from playlist
    path("playlist/<int:playlist_id>/add-song/<int:song_id>/", views.add_song_to_playlist, name="add_song_to_playlist"),
    path("playlist/<int:playlist_id>/remove-song/<int:song_id>/", views.remove_song_from_playlist, name="remove_song_from_playlist"),
    path("playlist/bulk-add/", views.bulk_add_songs_to_playlist, name="bulk_add_songs_to_playlist"),
    path("playlist/<int:playlist_id>/bulk-remove/", views.bulk_remove_songs_from_playlist, name="bulk_remove_songs_from_playlist"),
    
    # Subscription routes
    path('subscription/', views.subscription_page, name='subscription_page'),
    path('subscription/upgrade/', views.subscribe_premium, name='subscribe_premium'),
    path('subscription/khalti/callback/', views.khalti_subscription_callback, name='khalti_subscription_callback'),
    path('subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
    
    # Recommendation Algorithm routes
    path('recommendations/personalized/', views.personalized_recommendations, name='personalized_recommendations_page'),
    path('recommendations/collaborative/', views.collaborative_filtering_recommendations, name='collab_recommendations'),
    path('recommendations/content/', views.content_based_recommendations, name='content_recommendations'),
    path('api/recommendations/', views.get_recommendations_api, name='recommendations_api'),
    
    # New API endpoints for enhanced features
    # Like/Favorite system
    path('api/like-song/', api_views.like_song, name='like_song'),
    path('api/get-likes/', api_views.get_user_likes, name='get_likes'),
    
    # Listening history and tracking
    path('api/track-listening/', api_views.track_listening, name='track_listening'),
    path('api/recently-played/', api_views.get_recently_played, name='recently_played'),
    path('api/most-played/', api_views.get_most_played, name='most_played'),
    path('api/listening-stats/', api_views.get_listening_time_stats, name='listening_stats'),
    
    # Mood preferences
    path('api/set-mood-preference/', api_views.set_mood_preference, name='set_mood_preference'),
    
    # Advanced search
    path('api/search-advanced/', api_views.search_advanced, name='search_advanced'),
    
    # Playlist sharing
    path('api/playlist/<int:playlist_id>/share-link/', api_views.get_playlist_share_link, name='playlist_share_link'),
    path('api/playlist/<int:playlist_id>/toggle-visibility/', api_views.toggle_playlist_visibility, name='toggle_playlist_visibility'),
    
    # Personalized recommendations
    path('api/personalized-recommendations/', api_views.get_personalized_recommendations, name='personalized_recommendations'),
    
]
