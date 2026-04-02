from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView
from django.contrib.auth.decorators import login_required
# reverse_lazy not required here

urlpatterns = [
    path('', views.home, name='home'),
    path('home/', views.home, name='home'),
    path('sign-up', views.sign_up, name='sign_up'),
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
    path("playlist/create/", views.create_playlist, name="create_playlist"),
    path("playlist/<int:playlist_id>/", views.playlist_detail, name="playlist_detail"),
    path("playlist/<int:playlist_id>/edit/", views.edit_playlist, name="edit_playlist"),
    path("playlist/<int:playlist_id>/delete/", views.delete_playlist, name="delete_playlist"),
    
    # Add/Remove songs from playlist
    path("playlist/<int:playlist_id>/add-song/<int:song_id>/", views.add_song_to_playlist, name="add_song_to_playlist"),
    path("playlist/<int:playlist_id>/remove-song/<int:song_id>/", views.remove_song_from_playlist, name="remove_song_from_playlist"),
    path('playlists/compare/', views.compare_playlists, name='compare_playlists'),
    
    # Subscription routes
    path('subscription/', views.subscription_page, name='subscription_page'),
    path('subscription/upgrade/', views.subscribe_premium, name='subscribe_premium'),
    path('subscription/khalti/callback/', views.khalti_subscription_callback, name='khalti_subscription_callback'),
    path('subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
    
    # Recommendation Algorithm routes
    path('recommendations/collaborative/', views.collaborative_filtering_recommendations, name='collab_recommendations'),
    path('recommendations/content/', views.content_based_recommendations, name='content_recommendations'),
    path('api/recommendations/', views.get_recommendations_api, name='recommendations_api'),
]
