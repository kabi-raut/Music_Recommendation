from django.shortcuts import render, redirect, get_object_or_404
from .forms import RegisterForm
from .models import Playlist, Song, Genre, Subscription
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from .music_api import MusicAPIService, JamendoAPI, iTunesAPI, OpenSourceMusicAPI
from django.contrib import messages
from django.http import JsonResponse
from django.core.cache import cache
from django.conf import settings
from django.urls import reverse
import json
import urllib.request
import urllib.error
import uuid
from .recommendations import (
    CollaborativeFiltering,
    ContentBasedFiltering
)

# Create your views here.
def home(request):
    """Render the Finder home page."""
    return render(request, 'main/home.html')

def sign_up(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            # send newly-registered users to the public home page
            return redirect('home')
            
    else:
        form = RegisterForm()
    return render(request, 'registration/sign_up.html', {'form': form})

def songs_list(request):
    """Legacy songs route now serves live API music discovery."""
    return discover_music(request)



@login_required
def create_playlist(request):
    if request.method == "POST":
        name = request.POST.get("name")
        desc = request.POST.get("description")
        Playlist.objects.create(user=request.user, name=name, description=desc)
        return redirect("dashboard")
    return render(request, "main/playlist_create.html")

@login_required
def edit_playlist(request, playlist_id):
    playlist = Playlist.objects.get(id=playlist_id, user=request.user)

    if request.method == "POST":
        playlist.name = request.POST.get("name")
        playlist.description = request.POST.get("description")
        playlist.save()
        return redirect("dashboard")

    return render(request, "main/playlist_edit.html", {"playlist": playlist})

@login_required
def delete_playlist(request, playlist_id):
    playlist = Playlist.objects.get(id=playlist_id, user=request.user)
    playlist.delete()
    return redirect("dashboard")

@login_required
def playlist_detail(request, playlist_id):
    """View playlist details and songs in it."""
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    songs = playlist.songs.all()
    
    # Get subscription info
    subscription = Subscription.objects.get_or_create(user=request.user)[0]
    
    return render(request, "main/playlist_detail.html", {
        "playlist": playlist,
        "songs": songs,
        "subscription": subscription,
        "is_premium": subscription.is_premium(),
        "song_limit": subscription.get_playlist_song_limit(),
        "current_song_count": songs.count(),
    })

@login_required
def add_song_to_playlist(request, playlist_id, song_id):
    """Add a song to a playlist with subscription limit checking."""
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    song = get_object_or_404(Song, id=song_id)
    
    # Get user subscription
    subscription = Subscription.objects.get_or_create(user=request.user)[0]
    song_limit = subscription.get_playlist_song_limit()
    current_song_count = playlist.songs.count()
    
    # Check if adding song would exceed limit
    if not subscription.is_premium() and current_song_count >= song_limit:
        messages.error(request, f"Free users can only have {song_limit} songs per playlist. Upgrade to Premium for unlimited songs!")
        return redirect(request.META.get('HTTP_REFERER', 'songs_list'))
    
    if not playlist.songs.filter(id=song_id).exists():
        playlist.songs.add(song)
        messages.success(request, f"'{song.title}' added to {playlist.name}!")
    else:
        messages.info(request, "Song already in playlist")
    
    # Redirect back to the referrer or songs list
    return redirect(request.META.get('HTTP_REFERER', 'songs_list'))

@login_required
def remove_song_from_playlist(request, playlist_id, song_id):
    """Remove a song from a playlist."""
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    song = get_object_or_404(Song, id=song_id)
    
    playlist.songs.remove(song)
    
    # Redirect back to the referrer
    return redirect(request.META.get('HTTP_REFERER', 'songs_list'))


@login_required
def compare_playlists(request):
    """Compare two playlists from two users to find common and unique songs."""
    # User 1 is always the currently logged-in user.
    user_1_id = str(request.user.id)
    playlist_1_id = request.GET.get('p1')
    playlist_2_id = request.GET.get('p2')

    registered_users = User.objects.exclude(id=request.user.id).order_by('username')

    selected_user_1 = request.user
    selected_user_2 = None

    all_playlists = Playlist.objects.select_related('user').annotate(song_count=Count('songs')).order_by('user__username', 'name')
    user_1_playlists = all_playlists.filter(user=selected_user_1)
    user_2_playlists = all_playlists.exclude(user=selected_user_1)

    if not playlist_1_id and user_1_playlists.exists():
        playlist_1_id = str(user_1_playlists.first().id)

    selected_playlist_1 = user_1_playlists.filter(id=playlist_1_id).first() if playlist_1_id else None
    
    comparison_data = None
    if playlist_1_id and playlist_2_id:
        try:
            playlist_1 = get_object_or_404(Playlist, id=playlist_1_id, user=selected_user_1)
            playlist_2 = get_object_or_404(Playlist, id=playlist_2_id)
            if playlist_2.user_id == selected_user_1.id:
                raise ValueError('Second playlist must belong to a different user.')

            selected_user_2 = playlist_2.user
            
            # Get songs from both playlists
            songs_1 = set(playlist_1.songs.all())
            songs_2 = set(playlist_2.songs.all())
            
            # Calculate comparison
            common_songs = songs_1 & songs_2  # Intersection
            unique_to_1 = songs_1 - songs_2   # Only in playlist 1
            unique_to_2 = songs_2 - songs_1   # Only in playlist 2
            
            # Calculate similarity percentage
            total_songs = len(songs_1 | songs_2)
            similarity_percentage = (len(common_songs) / total_songs * 100) if total_songs > 0 else 0
            
            comparison_data = {
                'playlist_1': playlist_1,
                'playlist_2': playlist_2,
                'playlist_1_song_count': len(songs_1),
                'playlist_2_song_count': len(songs_2),
                'common_songs': sorted(common_songs, key=lambda s: s.title),
                'unique_to_1': sorted(unique_to_1, key=lambda s: s.title),
                'unique_to_2': sorted(unique_to_2, key=lambda s: s.title),
                'similarity_percentage': round(similarity_percentage, 1),
                'common_count': len(common_songs),
                'unique_1_count': len(unique_to_1),
                'unique_2_count': len(unique_to_2),
            }
        except Exception as e:
            messages.error(request, f'Error comparing playlists: {str(e)}')

    if selected_user_2 is None and playlist_2_id:
        playlist_2 = all_playlists.filter(id=playlist_2_id).first()
        if playlist_2 and playlist_2.user_id != selected_user_1.id:
            selected_user_2 = playlist_2.user
    
    context = {
        'registered_users': registered_users,
        'user_1': selected_user_1,
        'user_2': selected_user_2,
        'user_1_playlists': user_1_playlists,
        'user_2_playlists': user_2_playlists,
        'comparison': comparison_data,
        'selected_user_1': str(selected_user_1.id),
        'selected_playlist_1': selected_playlist_1,
        'selected_p1': playlist_1_id,
        'selected_p2': playlist_2_id,
    }
    
    return render(request, 'main/compare_playlists.html', context)


def discover_music(request):
    """
    Discover music dynamically from APIs (Jamendo, iTunes)
    This provides real-time streaming from external sources
    """
    songs = []
    recommended_songs = []  # For authenticated users
    search_query = request.GET.get('search', '')
    source_filter = request.GET.get('source', 'all')  # all, jamendo, itunes, opensource
    genre_filter = request.GET.get('genre', '')
    cache_key = f"discover:{source_filter}:{search_query.strip().lower()}:{genre_filter.strip().lower()}"

    cached_songs = cache.get(cache_key)
    if cached_songs is not None:
        songs = cached_songs
    else:
        try:
            if search_query:
                # Search across APIs
                if source_filter == 'jamendo':
                    songs = JamendoAPI.search_tracks(search_query, limit=16, genre=genre_filter)
                elif source_filter == 'itunes':
                    songs = iTunesAPI.search_tracks(search_query, limit=16)
                elif source_filter == 'opensource':
                    songs = OpenSourceMusicAPI.search_tracks(search_query, limit=16, genre=genre_filter)
                else:
                    songs = MusicAPIService.search_all(search_query, limit_per_source=6, genre=genre_filter)
            else:
                # Get trending/popular music by selected source
                if source_filter == 'jamendo':
                    songs = JamendoAPI.get_popular_tracks(limit=16)
                elif source_filter == 'opensource':
                    songs = OpenSourceMusicAPI.search_tracks(query="", limit=16, genre=genre_filter)
                elif source_filter == 'itunes':
                    # iTunes requires a query, so use a generic term for trending-like results.
                    songs = iTunesAPI.search_tracks('top music', limit=16)
                else:
                    songs = MusicAPIService.get_trending(limit=18)
        except Exception as e:
            messages.error(request, f"Error fetching music: {str(e)}")

        cache.set(cache_key, songs, 120)
    
    # Get content-based recommendations for authenticated users with playlists
    if request.user.is_authenticated:
        try:
            # Check if user has any songs in playlists
            user_has_playlists = Playlist.objects.filter(user=request.user).exists()
            if user_has_playlists:
                recommended_songs = ContentBasedFiltering.recommend_for_user(request.user, limit=8)
        except Exception as e:
            # If recommendation fails, just continue without personalized recommendations
            pass
    
    # Get user's playlists for adding songs
    user_playlists = []
    if request.user.is_authenticated:
        user_playlists = Playlist.objects.filter(user=request.user).annotate(song_count=Count('songs'))
    
    context = {
        'songs': songs,
        'recommended_songs': recommended_songs,  # Content-based recommendations
        'search_query': search_query,
        'source_filter': source_filter,
        'genre_filter': genre_filter,
        'user_playlists': user_playlists,
        'is_dynamic': True,  # Flag to indicate these are API songs
    }
    
    return render(request, 'main/discover_music.html', context)


def save_external_song(request):
    """
    Save an external API song to local database for playlist usage
    Receives AJAX request with song data
    """
    if request.method == 'POST':
        if not request.user.is_authenticated:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'code': 'auth_required',
                    'message': 'Your session expired. Please login again.'
                }, status=401)
            return redirect('login')

        try:
            raw_duration = request.POST.get('duration')
            try:
                duration_value = int(float(raw_duration)) if raw_duration not in (None, '') else None
            except (ValueError, TypeError):
                duration_value = None

            source = (request.POST.get('source') or 'opensource').lower().strip()
            if source not in {'jamendo', 'itunes', 'opensource', 'local'}:
                source = 'opensource'

            title = (request.POST.get('title') or 'Unknown Title').strip()
            artist = (request.POST.get('artist') or 'Unknown Artist').strip()
            external_id = (request.POST.get('external_id') or '').strip() or f"{source}:{title}:{artist}"

            song_data = {
                'title': title,
                'artist': artist,
                'genre_name': request.POST.get('genre'),
                'audio_url': request.POST.get('audio_url'),
                'cover_image_url': request.POST.get('cover_image'),
                'duration': duration_value,
                'external_id': external_id,
                'source': source,
            }
            
            if not song_data['audio_url']:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Selected song has no playable audio URL.'
                }, status=400)

            # Reuse an existing song when possible to prevent duplicate rows
            song = Song.objects.filter(external_id=external_id, source=source).first()
            if song is None:
                song = Song.objects.filter(
                    title__iexact=title,
                    artist__iexact=artist,
                    source=source,
                ).order_by('-created_at').first()

            if song is None:
                song = Song.objects.create(**song_data)
            else:
                updated_fields = []
                if not song.audio_url and song_data.get('audio_url'):
                    song.audio_url = song_data['audio_url']
                    updated_fields.append('audio_url')
                if not song.cover_image_url and song_data.get('cover_image_url'):
                    song.cover_image_url = song_data['cover_image_url']
                    updated_fields.append('cover_image_url')
                if not song.genre_name and song_data.get('genre_name'):
                    song.genre_name = song_data['genre_name']
                    updated_fields.append('genre_name')
                if not song.duration and song_data.get('duration'):
                    song.duration = song_data['duration']
                    updated_fields.append('duration')
                if updated_fields:
                    song.save(update_fields=updated_fields)
            
            # If playlist_id provided, add to playlist
            playlist_id = request.POST.get('playlist_id')
            if playlist_id:
                playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
                
                # Check subscription limit
                subscription = Subscription.objects.get_or_create(user=request.user)[0]
                song_limit = subscription.get_playlist_song_limit()
                current_song_count = playlist.songs.count()
                
                if not subscription.is_premium() and current_song_count >= song_limit:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Free users can only have {song_limit} songs per playlist. Upgrade to Premium for unlimited songs!'
                    }, status=400)
                
                duplicate_exists = playlist.songs.filter(
                    Q(id=song.id) |
                    Q(title__iexact=title, artist__iexact=artist, source=source)
                ).exists()

                if not duplicate_exists:
                    playlist.songs.add(song)
                    updated_count = playlist.songs.count()
                    return JsonResponse({
                        'status': 'success',
                        'message': f'Added "{song.title}" to {playlist.name}!',
                        'song_id': song.id,
                        'playlist_id': playlist.id,
                        'playlist_song_count': updated_count,
                    })
                else:
                    current_count = playlist.songs.count()
                    return JsonResponse({
                        'status': 'info',
                        'message': 'Song already in playlist',
                        'playlist_id': playlist.id,
                        'playlist_song_count': current_count,
                    })
            
            return JsonResponse({
                'status': 'success',
                'message': 'Song saved successfully!',
                'song_id': song.id
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


def browse_by_source(request, source):
    """
    Browse music by source (jamendo, itunes, or opensource)
    """
    songs = []
    genre = request.GET.get('genre', '')
    
    try:
        if source == 'jamendo':
            songs = JamendoAPI.search_tracks(genre=genre, limit=30)
        elif source == 'itunes' and genre:
            songs = iTunesAPI.search_tracks(genre, limit=30)
        elif source == 'opensource':
            from .music_api import OpenSourceMusicAPI
            songs = OpenSourceMusicAPI.search_tracks(genre=genre, limit=30)
        else:
            messages.info(request, "Please select a genre or use the search")
    except Exception as e:
        messages.error(request, f"Error fetching music: {str(e)}")
    
    context = {
        'songs': songs,
        'source': source,
        'genre_filter': genre,
        'is_dynamic': True,
    }
    
    return render(request, 'main/browse_source.html', context)


# ==================== RECOMMENDATION ALGORITHMS ====================

@login_required
def collaborative_filtering_recommendations(request):
    """
    View for Collaborative Filtering Recommendations
    Shows songs recommended based on similar users' preferences
    Premium feature
    """
    subscription = Subscription.objects.get_or_create(user=request.user)[0]
    
    if not subscription.is_premium():
        messages.warning(request, 'Advanced recommendations are a Premium feature. Upgrade to Premium to unlock AI-powered recommendations!')
        return redirect('subscription_page')
    
    recommended_songs = CollaborativeFiltering.recommend_for_user(request.user, limit=15)
    similar_users = CollaborativeFiltering.get_similar_users(request.user, limit=5)
    
    user_playlists = Playlist.objects.filter(user=request.user)
    
    context = {
        'songs': recommended_songs,
        'algorithm': 'Collaborative Filtering',
        'description': 'Based on what users with similar taste enjoyed',
        'similar_users': similar_users,
        'user_playlists': user_playlists,
        'recommendation_type': 'collaborative',
        'subscription': subscription,
    }
    
    return render(request, 'main/recommendations.html', context)


@login_required
def content_based_recommendations(request):
    """
    View for Content-Based Filtering Recommendations
    Shows songs recommended based on genres and artists user likes
    Premium feature
    """
    subscription = Subscription.objects.get_or_create(user=request.user)[0]
    
    if not subscription.is_premium():
        messages.warning(request, 'Advanced recommendations are a Premium feature. Upgrade to Premium to unlock AI-powered recommendations!')
        return redirect('subscription_page')
    
    recommended_songs = ContentBasedFiltering.recommend_for_user(request.user, limit=15)
    
    user_playlists = Playlist.objects.filter(user=request.user)
    
    context = {
        'songs': recommended_songs,
        'algorithm': 'Content-Based Filtering',
        'description': 'Based on genres and artists in your playlists',
        'user_playlists': user_playlists,
        'recommendation_type': 'content',
        'subscription': subscription,
    }
    
    return render(request, 'main/recommendations.html', context)


@login_required
def get_recommendations_api(request):
    """
    API endpoint for getting recommendations
    Accepts method parameter: 'collaborative' or 'content'
    Returns JSON response with recommended songs
    """
    method = request.GET.get('method', 'content')
    limit = int(request.GET.get('limit', 10))
    
    try:
        if method == 'collaborative':
            songs = CollaborativeFiltering.recommend_for_user(request.user, limit=limit)
        elif method == 'content':
            songs = ContentBasedFiltering.recommend_for_user(request.user, limit=limit)
        else:
            return JsonResponse({
                'status': 'error',
                'message': f'Unknown recommendation method: {method}'
            }, status=400)
        
        # Convert songs to JSON
        songs_data = [
            {
                'id': song.id,
                'title': song.title,
                'artist': song.artist,
                'genre': song.get_genre_display(),
                'audio_url': song.get_audio_source(),
                'cover_image': song.get_cover_image(),
                'source': song.source,
            }
            for song in songs
        ]
        
        return JsonResponse({
            'status': 'success',
            'method': method,
            'count': len(songs_data),
            'songs': songs_data
        })
    
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)


# ==================== SUBSCRIPTION MANAGEMENT ====================

@login_required
def subscription_page(request):
    """Display user subscription status and upgrade options"""
    subscription = Subscription.objects.get_or_create(user=request.user)[0]
    
    context = {
        'subscription': subscription,
        'is_premium': subscription.is_premium(),
        'song_limit': subscription.get_playlist_song_limit(),
        'khalti_public_key': settings.KHALTI_PUBLIC_KEY,
        'khalti_mode': settings.KHALTI_MODE,
    }
    
    return render(request, 'main/subscription.html', context)


def _khalti_post_json(url, payload, secret_key):
    """Send JSON POST request to Khalti and return parsed JSON response."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Key {secret_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Khalti API error ({exc.code}): {body}')
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Unable to connect to Khalti: {exc.reason}')


@login_required
def subscribe_premium(request):
    """Start Khalti payment for premium subscription."""
    if request.method == 'POST':
        try:
            duration_days = int(request.POST.get('duration', 30))

            if not settings.KHALTI_SECRET_KEY:
                messages.error(request, 'Khalti secret key is not configured.')
                return redirect('subscription_page')

            price_map_paisa = {
                30: 49900,
                90: 129900,
                365: 449900,
            }
            amount_paisa = price_map_paisa.get(duration_days, 49900)

            purchase_order_id = f'sub-{request.user.id}-{duration_days}-{uuid.uuid4().hex[:10]}'

            if settings.KHALTI_RETURN_URL_BASE:
                return_url = f"{settings.KHALTI_RETURN_URL_BASE.rstrip('/')}{reverse('khalti_subscription_callback')}"
            else:
                return_url = request.build_absolute_uri(reverse('khalti_subscription_callback'))

            website_url = settings.KHALTI_WEBSITE_URL or request.build_absolute_uri('/')

            payload = {
                'return_url': return_url,
                'website_url': website_url,
                'amount': amount_paisa,
                'purchase_order_id': purchase_order_id,
                'purchase_order_name': f'Premium Subscription ({duration_days} days)',
                'customer_info': {
                    'name': request.user.get_full_name() or request.user.username,
                    'email': request.user.email or 'sandbox@example.com',
                    'phone': '9800000000',
                },
            }

            response_data = _khalti_post_json(
                settings.KHALTI_INITIATE_URL,
                payload,
                settings.KHALTI_SECRET_KEY,
            )

            payment_url = response_data.get('payment_url')
            pidx = response_data.get('pidx')

            if not payment_url or not pidx:
                raise RuntimeError('Khalti did not return payment_url/pidx for checkout.')

            request.session['khalti_subscription_meta'] = {
                'purchase_order_id': purchase_order_id,
                'duration_days': duration_days,
            }

            return redirect(payment_url)
        except Exception as e:
            messages.error(request, f'Error starting Khalti payment: {str(e)}')
            return redirect('subscription_page')
    
    return redirect('subscription_page')


@login_required
def khalti_subscription_callback(request):
    """Verify Khalti payment callback and activate premium."""
    pidx = request.GET.get('pidx')
    status = request.GET.get('status')

    if not pidx:
        messages.error(request, 'Missing Khalti payment reference (pidx).')
        return redirect('subscription_page')

    if status and status.lower() != 'completed':
        messages.warning(request, f'Khalti payment status: {status}. Premium was not activated.')
        return redirect('subscription_page')

    try:
        if not settings.KHALTI_SECRET_KEY:
            messages.error(request, 'Khalti secret key is not configured.')
            return redirect('subscription_page')

        lookup_payload = {'pidx': pidx}
        lookup_data = _khalti_post_json(
            settings.KHALTI_LOOKUP_URL,
            lookup_payload,
            settings.KHALTI_SECRET_KEY,
        )

        if lookup_data.get('status') != 'Completed':
            messages.warning(
                request,
                f"Khalti verification status: {lookup_data.get('status', 'Unknown')}. Premium was not activated.",
            )
            return redirect('subscription_page')

        meta = request.session.pop('khalti_subscription_meta', {})
        duration_days = int(meta.get('duration_days', 30))

        subscription = Subscription.objects.get_or_create(user=request.user)[0]
        subscription.activate_premium(duration_days=duration_days)

        messages.success(request, 'Khalti payment verified. Premium subscription is now active!')
        return redirect('subscription_page')

    except Exception as e:
        messages.error(request, f'Error verifying Khalti payment: {str(e)}')
        return redirect('subscription_page')


@login_required
def cancel_subscription(request):
    """Cancel premium subscription"""
    if request.method == 'POST':
        try:
            subscription = Subscription.objects.get_or_create(user=request.user)[0]
            subscription.cancel_subscription()
            
            messages.warning(request, 'Your Premium subscription has been cancelled. You now have access only to free features.')
            return redirect('subscription_page')
        except Exception as e:
            messages.error(request, f'Error cancelling subscription: {str(e)}')
            return redirect('subscription_page')
    
    return redirect('subscription_page')


@login_required
def dashboard(request):
    """Enhanced dashboard with subscription info"""
    playlists = Playlist.objects.filter(user=request.user).annotate(song_count=Count('songs'))
    subscription = Subscription.objects.get_or_create(user=request.user)[0]
    
    return render(request, "main/dashboard.html", {
        "playlists": playlists,
        "subscription": subscription,
        "is_premium": subscription.is_premium(),
    })
