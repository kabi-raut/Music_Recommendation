from django.shortcuts import render, redirect, get_object_or_404
from .forms import RegisterForm, UserProfileForm, ForgotPasswordRequestForm, OTPVerificationForm
from .models import (
    Playlist,
    Song,
    SongLike,
    Subscription,
    SubscriptionPlan,
    PaymentRecord,
    SubscriptionChangeLog,
    AdminActionLog,
    SearchHistory,
)
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from .music_api import iTunesAPI
from django.contrib import messages
from django.http import JsonResponse
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
import json
import urllib.request
import urllib.error
import uuid
import random
from decimal import Decimal
from datetime import timedelta, datetime
from .recommendations import (
    CollaborativeFiltering,
    ContentBasedFiltering
)
from .hybrid_recommendation import HybridRecommendationEngine, RecommendationExplainer

# Operations admin credentials are loaded from Django settings.
ADMIN_PORTAL_USERNAME = getattr(settings, 'OPS_ADMIN_USERNAME', '').strip()
ADMIN_PORTAL_PASSWORD = getattr(settings, 'OPS_ADMIN_PASSWORD', '').strip()

PASSWORD_RESET_OTP_TTL_SECONDS = 10 * 60
PASSWORD_RESET_OTP_MAX_ATTEMPTS = 5


def _mask_email(email):
    if '@' not in email:
        return email
    local_part, domain = email.split('@', 1)
    if len(local_part) <= 2:
        masked_local = local_part[0] + '*' * (len(local_part) - 1)
    else:
        masked_local = local_part[0] + '*' * (len(local_part) - 2) + local_part[-1]
    return f"{masked_local}@{domain}"


def _send_password_reset_otp(user):
    otp = f"{random.randint(0, 999999):06d}"
    challenge_id = uuid.uuid4().hex
    expires_at = timezone.now() + timedelta(seconds=PASSWORD_RESET_OTP_TTL_SECONDS)

    cache.set(
        f'password-reset-otp:{challenge_id}',
        {
            'user_id': user.id,
            'otp': otp,
            'attempts': 0,
        },
        timeout=PASSWORD_RESET_OTP_TTL_SECONDS,
    )

    subject = 'Finder Password Reset OTP'
    message = (
        f"Hello {user.get_full_name() or user.username},\n\n"
        f"Your Finder password reset OTP is: {otp}\n"
        f"This OTP is valid for 10 minutes.\n\n"
        "If you did not request this, you can ignore this email."
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

    return challenge_id, expires_at


def _log_subscription_change(
    user,
    previous_tier,
    new_tier,
    previous_plan,
    new_plan,
    source='system',
    notes='',
    changed_by=None,
):
    """Store a subscription audit record when tier or plan changes."""
    previous_plan_id = previous_plan.id if previous_plan else None
    new_plan_id = new_plan.id if new_plan else None
    if previous_tier == new_tier and previous_plan_id == new_plan_id:
        return

    SubscriptionChangeLog.objects.create(
        user=user,
        previous_tier=previous_tier or '',
        new_tier=new_tier,
        previous_plan=previous_plan,
        new_plan=new_plan,
        source=source,
        notes=notes,
        changed_by=changed_by,
    )


def _log_admin_action(actor, action, target_type='', target_label='', details=''):
    AdminActionLog.objects.create(
        actor=actor if actor and actor.is_authenticated else None,
        action=action,
        target_type=target_type,
        target_label=target_label,
        details=details,
    )


def _activate_subscription_for_payment(payment_record, source='admin_update'):
    subscription, _ = Subscription.objects.get_or_create(user=payment_record.user)
    previous_tier = subscription.tier
    previous_plan = subscription.plan

    subscription.tier = 'premium'
    subscription.is_active = True
    if payment_record.plan:
        subscription.plan = payment_record.plan
    if not subscription.expiry_date or subscription.expiry_date <= timezone.now():
        plan_days = (
            payment_record.plan.duration_days
            if payment_record.plan
            else getattr(settings, 'SUBSCRIPTION_DURATION_DAYS', 30)
        )
        subscription.expiry_date = timezone.now() + timedelta(days=plan_days)

    subscription.save()
    _log_subscription_change(
        user=payment_record.user,
        previous_tier=previous_tier,
        new_tier=subscription.tier,
        previous_plan=previous_plan,
        new_plan=subscription.plan,
        source=source,
        notes=f'Payment record {payment_record.id} marked as completed.',
    )


def _finalize_payment_record(payment_record, *, source='admin_update', status='completed'):
    payment_record.status = status
    payment_record.save(update_fields=['status'])

    if status == 'completed' and payment_record.user_id:
        _activate_subscription_for_payment(payment_record, source=source)


def _retry_khalti_payment_lookup(payment_record):
    if payment_record.provider != 'khalti' or not payment_record.provider_reference:
        return False, 'This payment cannot be retried with Khalti lookup.'

    lookup_payload = {'pidx': payment_record.provider_reference}
    try:
        response_data = _khalti_post_json(settings.KHALTI_LOOKUP_URL, lookup_payload, settings.KHALTI_SECRET_KEY)
    except Exception as exc:
        return False, f'Khalti lookup failed: {exc}'

    if response_data.get('status') == 'Completed':
        _finalize_payment_record(payment_record, source='khalti_webhook_retry', status='completed')
        return True, 'Payment confirmed through Khalti lookup.'

    if response_data.get('status') in {'Pending', 'Initiated'}:
        payment_record.status = 'pending'
        payment_record.save(update_fields=['status'])
        return False, 'Payment is still pending in Khalti.'

    payment_record.status = 'failed'
    payment_record.save(update_fields=['status'])
    return False, f"Khalti returned status '{response_data.get('status', 'unknown')}'."

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


def unified_login(request):
    """Single login page for regular users and environment-backed admin credentials."""
    if request.user.is_authenticated:
        if request.user.is_superuser:
            request.session['ops_admin_authenticated'] = True
        return redirect('dashboard')

    next_url = request.POST.get('next') or request.GET.get('next', '')

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''

        # Allow the documented hardcoded credentials to enter the ops admin portal.
        if username == ADMIN_PORTAL_USERNAME and password == ADMIN_PORTAL_PASSWORD:
            request.session['ops_admin_authenticated'] = True
            fallback_user = authenticate(request, username=username, password=password)
            if fallback_user is not None and fallback_user.is_active:
                login(request, fallback_user)
            return redirect('admin_portal')

        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            authenticated_user = form.get_user()
            login(request, authenticated_user)
            if authenticated_user.is_superuser:
                request.session['ops_admin_authenticated'] = True
            if next_url:
                return redirect(next_url)
            if authenticated_user.is_superuser:
                return redirect('admin_portal')
            return redirect('dashboard')
    else:
        form = AuthenticationForm(request)

    context = {
        'form': form,
        'next': next_url,
        'password_reset_success': request.GET.get('reset') == 'success',
    }
    return render(request, 'registration/login.html', context)


def forgot_password_request(request):
    """Start password reset flow by sending a 6-digit OTP to the user's email."""
    email_hint = ''
    if request.method == 'POST':
        form = ForgotPasswordRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            user = User.objects.filter(email__iexact=email).first()

            if user:
                challenge_id, expires_at = _send_password_reset_otp(user)
                request.session['password_reset_challenge_id'] = challenge_id
                request.session['password_reset_email'] = user.email
                request.session['password_reset_otp_expires_at'] = expires_at.isoformat()
                request.session.pop('password_reset_verified_token', None)

                email_hint = _mask_email(user.email)
                return redirect('verify_password_otp')

            form.add_error('email', 'No account found with this email address.')
    else:
        form = ForgotPasswordRequestForm()

    context = {
        'form': form,
        'email_hint': email_hint,
    }
    return render(request, 'registration/forgot_password.html', context)


def resend_password_otp(request):
    """Resend a fresh OTP to the user while keeping the reset session alive."""
    if request.method != 'POST':
        return redirect('forgot_password')

    email = (request.session.get('password_reset_email') or '').strip()
    if not email:
        messages.error(request, 'Your password reset session expired. Request a new OTP.')
        return redirect('forgot_password')

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        request.session.pop('password_reset_challenge_id', None)
        request.session.pop('password_reset_email', None)
        request.session.pop('password_reset_otp_expires_at', None)
        messages.error(request, 'No matching account found. Request a new OTP.')
        return redirect('forgot_password')

    challenge_id, expires_at = _send_password_reset_otp(user)
    request.session['password_reset_challenge_id'] = challenge_id
    request.session['password_reset_email'] = user.email
    request.session['password_reset_otp_expires_at'] = expires_at.isoformat()
    request.session.pop('password_reset_verified_token', None)

    messages.success(request, 'A new OTP has been sent to your email address.')
    return redirect('verify_password_otp')


def verify_password_otp(request):
    """Verify OTP sent to user's email before allowing password reset."""
    challenge_id = request.session.get('password_reset_challenge_id')
    email = (request.session.get('password_reset_email') or '').strip()
    expires_at_raw = request.session.get('password_reset_otp_expires_at')
    expires_at_iso = expires_at_raw or ''
    otp_expired = False
    remaining_seconds = 0

    if expires_at_raw:
        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
            if timezone.is_naive(expires_at):
                expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())
            remaining_seconds = max(0, int((expires_at - timezone.now()).total_seconds()))
            otp_expired = remaining_seconds <= 0
        except ValueError:
            otp_expired = False

    if not challenge_id and not email:
        return redirect('forgot_password')

    cache_key = f'password-reset-otp:{challenge_id}' if challenge_id else None
    payload = cache.get(cache_key) if cache_key else None
    if not payload:
        otp_expired = True
        request.session.pop('password_reset_challenge_id', None)
        challenge_id = ''
        remaining_seconds = 0

    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            if otp_expired or not payload:
                form.add_error('otp', 'This OTP has expired. Please resend a new one.')
            else:
                submitted_otp = form.cleaned_data['otp']

                if submitted_otp == payload.get('otp'):
                    verification_token = uuid.uuid4().hex
                    cache.set(
                        f'password-reset-verified:{verification_token}',
                        {'user_id': payload.get('user_id')},
                        timeout=PASSWORD_RESET_OTP_TTL_SECONDS,
                    )
                    cache.delete(cache_key)
                    request.session.pop('password_reset_challenge_id', None)
                    request.session.pop('password_reset_email', None)
                    request.session.pop('password_reset_otp_expires_at', None)
                    request.session['password_reset_verified_token'] = verification_token
                    return redirect('reset_password_otp')

                payload['attempts'] = int(payload.get('attempts', 0)) + 1
                if payload['attempts'] >= PASSWORD_RESET_OTP_MAX_ATTEMPTS:
                    cache.delete(cache_key)
                    request.session.pop('password_reset_challenge_id', None)
                    form.add_error('otp', 'Too many incorrect attempts. Request a new OTP.')
                else:
                    cache.set(cache_key, payload, timeout=PASSWORD_RESET_OTP_TTL_SECONDS)
                    remaining = PASSWORD_RESET_OTP_MAX_ATTEMPTS - payload['attempts']
                    form.add_error('otp', f'Invalid OTP. {remaining} attempt(s) remaining.')
    else:
        form = OTPVerificationForm()

    user = User.objects.filter(email__iexact=email).first()
    if not email and payload:
        user = User.objects.filter(id=payload.get('user_id')).first()
    email_hint = _mask_email(user.email) if user and user.email else ''

    return render(
        request,
        'registration/verify_password_otp.html',
        {
            'form': form,
            'email_hint': email_hint,
            'otp_expired': otp_expired,
            'otp_expires_at': expires_at_iso,
            'remaining_seconds': remaining_seconds,
        },
    )


def reset_password_otp(request):
    """Allow user to set a new password after successful OTP verification."""
    verification_token = request.session.get('password_reset_verified_token')
    if not verification_token:
        return redirect('forgot_password')

    payload = cache.get(f'password-reset-verified:{verification_token}')
    if not payload:
        request.session.pop('password_reset_verified_token', None)
        return redirect('forgot_password')

    user = User.objects.filter(id=payload.get('user_id')).first()
    if not user:
        cache.delete(f'password-reset-verified:{verification_token}')
        request.session.pop('password_reset_verified_token', None)
        return redirect('forgot_password')

    if request.method == 'POST':
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            cache.delete(f'password-reset-verified:{verification_token}')
            request.session.pop('password_reset_verified_token', None)
            request.session.pop('password_reset_email', None)
            request.session.pop('password_reset_otp_expires_at', None)
            return redirect(f"{reverse('login')}?reset=success")
    else:
        form = SetPasswordForm(user)

    return render(request, 'registration/reset_password_otp.html', {'form': form})


@login_required
def edit_profile(request):
    """Allow users to edit their account details."""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('dashboard')
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'main/edit_profile.html', {'form': form})

def songs_list(request):
    """Legacy songs route now serves live API music discovery."""
    return discover_music(request)



@login_required
def create_playlist(request):
    subscription = Subscription.objects.get_or_create(user=request.user)[0]
    playlist_limit = subscription.get_playlist_limit()
    current_playlists = Playlist.objects.filter(user=request.user).count()

    if request.method == "POST":
        if current_playlists >= playlist_limit:
            messages.error(
                request,
                (
                    f"Your current subscription allows up to {int(playlist_limit)} "
                    "playlists. Upgrade to premium for more playlists."
                ),
            )
            return redirect("dashboard")

        name = request.POST.get("name")
        desc = request.POST.get("description")
        Playlist.objects.create(user=request.user, name=name, description=desc)
        return redirect("dashboard")
    return render(
        request,
        "main/playlist_create.html",
        {
            "playlist_limit": playlist_limit,
            "current_playlists": current_playlists,
            "subscription": subscription,
        },
    )

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
    liked_song_ids = list(
        SongLike.objects.filter(user=request.user, song__in=songs).values_list('song_id', flat=True)
    )
    
    # Get subscription info
    subscription = Subscription.objects.get_or_create(user=request.user)[0]
    
    return render(request, "main/playlist_detail.html", {
        "playlist": playlist,
        "songs": songs,
        "liked_song_ids": liked_song_ids,
        "subscription": subscription,
        "is_premium": subscription.is_premium(),
        "song_limit": subscription.get_playlist_song_limit(),
        "current_song_count": songs.count(),
        "playlist_limit": subscription.get_playlist_limit(),
    })


def public_playlist_view(request, share_link):
    """Public playlist page for shared playlists."""
    playlist = get_object_or_404(Playlist.objects.select_related('user'), share_link=share_link, is_public=True)
    songs = playlist.songs.all()
    owner_liked_song_ids = list(
        SongLike.objects.filter(user=playlist.user, song__in=songs).values_list('song_id', flat=True)
    )

    return render(
        request,
        "main/public_playlist.html",
        {
            "playlist": playlist,
            "songs": songs,
            "owner": playlist.user,
            "owner_liked_song_ids": owner_liked_song_ids,
            "is_shared_view": True,
        },
    )

@login_required
def add_song_to_playlist(request, playlist_id, song_id):
    """Add a song to a playlist with subscription limit checking."""
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    song = get_object_or_404(Song, id=song_id)
    
    # Get user subscription
    subscription = Subscription.objects.get_or_create(user=request.user)[0]
    song_limit = subscription.get_playlist_song_limit()
    current_song_count = playlist.songs.count()
    
    # Enforce subscription limits.
    if current_song_count >= song_limit:
        messages.error(request, f"Your current subscription allows up to {song_limit} songs per playlist.")
        return redirect(request.META.get('HTTP_REFERER', 'songs_list'))
    
    if not playlist.songs.filter(id=song_id).exists():
        playlist.songs.add(song)
        messages.success(request, f"'{song.title}' added to {playlist.name}!")
    else:
        messages.info(request, "Song already in playlist")
    
    # Redirect back to the referrer or songs list
    return redirect(request.META.get('HTTP_REFERER', 'songs_list'))


@login_required
def bulk_add_songs_to_playlist(request):
    """Add multiple songs to a playlist in one action."""
    if request.method != 'POST':
        return redirect(request.META.get('HTTP_REFERER', 'songs_list'))

    playlist_id = request.POST.get('playlist_id')
    song_ids = request.POST.getlist('song_ids')

    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    subscription = Subscription.objects.get_or_create(user=request.user)[0]
    song_limit = subscription.get_playlist_song_limit()

    if not song_ids:
        messages.info(request, 'Select at least one song to add.')
        return redirect(request.META.get('HTTP_REFERER', 'songs_list'))

    current_song_count = playlist.songs.count()
    added_count = 0
    skipped_count = 0

    for song_id in song_ids:
        if current_song_count >= song_limit:
            break

        song = Song.objects.filter(id=song_id).first()
        if song is None:
            continue

        if playlist.songs.filter(id=song.id).exists():
            skipped_count += 1
            continue

        playlist.songs.add(song)
        current_song_count += 1
        added_count += 1

    if added_count:
        messages.success(request, f'Added {added_count} song{"s" if added_count != 1 else ""} to {playlist.name}.')
    if skipped_count:
        messages.info(request, f'Skipped {skipped_count} duplicate song{"s" if skipped_count != 1 else ""}.')
    if current_song_count >= song_limit and len(song_ids) > added_count:
        messages.warning(request, f'Playlist limit reached at {song_limit} songs.')

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
def bulk_remove_songs_from_playlist(request, playlist_id):
    """Remove multiple songs from a playlist in one action."""
    if request.method != 'POST':
        return redirect(request.META.get('HTTP_REFERER', 'songs_list'))

    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    song_ids = request.POST.getlist('song_ids')

    if not song_ids:
        messages.info(request, 'Select at least one song to remove.')
        return redirect(request.META.get('HTTP_REFERER', 'songs_list'))

    removed_count = 0
    for song in Song.objects.filter(id__in=song_ids):
        if playlist.songs.filter(id=song.id).exists():
            playlist.songs.remove(song)
            removed_count += 1

    if removed_count:
        messages.success(
            request,
            f'Removed {removed_count} song{"s" if removed_count != 1 else ""} from {playlist.name}.',
        )
    else:
        messages.info(request, 'No matching songs were removed.')

    return redirect(request.META.get('HTTP_REFERER', reverse('playlist_detail', args=[playlist.id])))


def discover_music(request):
    """
    Discover music dynamically from iTunes only.
    """
    songs = []
    recommended_songs = []  # For authenticated users
    search_query = request.GET.get('search', '')
    source_filter = (request.GET.get('source') or '').strip().lower()
    if source_filter != 'itunes':
        source_filter = 'itunes'
    genre_filter = request.GET.get('genre', '')
    cache_key = f"discover:{source_filter}:{search_query.strip().lower()}:{genre_filter.strip().lower()}"

    cached_songs = cache.get(cache_key)
    if cached_songs is not None:
        songs = cached_songs
    else:
        try:
            if search_query:
                songs = iTunesAPI.search_tracks(search_query, limit=16, genre=genre_filter, raise_on_error=True)
            else:
                if genre_filter:
                    songs = iTunesAPI.search_tracks(query="", limit=16, genre=genre_filter, raise_on_error=True)
                else:
                    songs = []
        except Exception as e:
            error_text = str(e)
            messages.error(request, f"Error fetching music: {error_text}")

        cache.set(cache_key, songs, 120)

    # Track search history for authenticated users
    if request.user.is_authenticated and search_query:
        SearchHistory.objects.create(
            user=request.user,
            query=search_query,
            source_filter=source_filter,
            genre_filter=genre_filter,
            results_count=len(songs),
        )
    
    # Get personalized recommendations for authenticated users.
    # ContentBasedFiltering handles both regular and cold-start users.
    if request.user.is_authenticated:
        try:
            recommended_songs = ContentBasedFiltering.recommend_for_user(request.user, limit=8)
        except Exception:
            # If recommendation fails, just continue without personalized recommendations
            pass
    
    # Get user's playlists for adding songs
    user_playlists = []
    subscription = None
    user_playlist_song_ids = []
    liked_song_ids = []
    if request.user.is_authenticated:
        user_playlists = Playlist.objects.filter(user=request.user).annotate(song_count=Count('songs'))
        subscription = Subscription.objects.get_or_create(user=request.user)[0]
        user_playlist_song_ids = list(
            Playlist.objects.filter(user=request.user).values_list('songs__id', flat=True).distinct()
        )
        liked_song_ids = list(
            SongLike.objects.filter(user=request.user).values_list('song_id', flat=True)
        )
    
    context = {
        'songs': songs,
        'recommended_songs': recommended_songs,  # Content-based recommendations
        'search_query': search_query,
        'source_filter': source_filter,
        'genre_filter': genre_filter,
        'user_playlists': user_playlists,
        'user_playlist_song_ids': user_playlist_song_ids,
        'liked_song_ids': liked_song_ids,
        'is_dynamic': True,  # Flag to indicate these are API songs
        'subscription': subscription,
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

            source = (request.POST.get('source') or 'itunes').lower().strip()
            if source not in {'itunes', 'local'}:
                source = 'itunes'

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
                
                if current_song_count >= song_limit:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Your current subscription allows up to {song_limit} songs per playlist.'
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
    Browse music by source (iTunes only)
    """
    songs = []
    genre = request.GET.get('genre', '')
    source = 'itunes'
    
    try:
        songs = iTunesAPI.search_tracks(query='', genre=genre, limit=30, raise_on_error=True)
    except Exception as e:
        error_text = str(e)
        messages.error(request, f"Error fetching music: {error_text}")
    
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
    
    if not subscription.can_use_advanced_recommendations():
        messages.warning(request, 'Advanced recommendations require an active premium subscription.')
        return redirect('subscription_page')

    user_playlists = Playlist.objects.filter(user=request.user)
    has_playlist_songs = Song.objects.filter(playlists__user=request.user).exists()
    if not has_playlist_songs:
        context = {
            'songs': [],
            'explained_songs': [],
            'algorithm': 'Collaborative Filtering',
            'description': 'Based on what users with similar taste enjoyed',
            'similar_users': [],
            'user_playlists': user_playlists,
            'recommendation_type': 'collaborative',
            'subscription': subscription,
            'no_playlist_recommendation_guard': True,
            'empty_recommendation_message': (
                'Collaborative recommendations need songs in your playlists first. '
                'Add songs so we can find users with similar taste.'
            ),
        }
        return render(request, 'main/recommendations.html', context)
    
    recommended_songs = CollaborativeFiltering.recommend_for_user(
        request.user,
        limit=15,
        fallback_to_content=False,
    )
    similar_users = CollaborativeFiltering.get_similar_users(request.user, limit=5)
    user_genres = set(
        Song.objects.filter(playlists__user=request.user).values_list('genre_name', flat=True)
    )

    explained_songs = []
    for song in recommended_songs:
        reasons = []
        if song.genre_name and song.genre_name in user_genres:
            reasons.append(f"Matches your frequent genre: {song.genre_name}")
        if similar_users:
            reasons.append("Popular among users with similar playlists")
        if not reasons:
            reasons.append("Similar users interacted with this track")
        explained_songs.append({
            'song': song,
            'reason': reasons[0],
            'confidence': 'High' if len(reasons) > 1 else 'Medium',
        })
    
    context = {
        'songs': recommended_songs,
        'explained_songs': explained_songs,
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
    
    if not subscription.can_use_advanced_recommendations():
        messages.warning(request, 'Advanced recommendations require an active premium subscription.')
        return redirect('subscription_page')
    
    recommended_songs = ContentBasedFiltering.recommend_for_user(request.user, limit=15)
    user_genres = set(
        Song.objects.filter(playlists__user=request.user).values_list('genre_name', flat=True)
    )
    user_artists = set(
        Song.objects.filter(playlists__user=request.user).values_list('artist', flat=True)
    )

    explained_songs = []
    for song in recommended_songs:
        if song.genre_name and song.genre_name in user_genres:
            reason = f"Because you like {song.genre_name} music"
            confidence = 'High'
        elif song.artist and song.artist in user_artists:
            reason = f"Because you listen to {song.artist}"
            confidence = 'High'
        else:
            reason = "Similar to songs in your playlists"
            confidence = 'Medium'
        explained_songs.append({
            'song': song,
            'reason': reason,
            'confidence': confidence,
        })
    
    user_playlists = Playlist.objects.filter(user=request.user)
    
    context = {
        'songs': recommended_songs,
        'explained_songs': explained_songs,
        'algorithm': 'Content-Based Filtering',
        'description': 'Based on genres and artists in your playlists',
        'user_playlists': user_playlists,
        'recommendation_type': 'content',
        'subscription': subscription,
    }
    
    return render(request, 'main/recommendations.html', context)


@login_required
def personalized_recommendations(request):
    """Direct hybrid recommendations that combine collaborative, content-based, and contextual signals."""
    subscription = Subscription.objects.get_or_create(user=request.user)[0]

    if not subscription.can_use_advanced_recommendations():
        messages.warning(request, 'Advanced recommendations require an active premium subscription.')
        return redirect('subscription_page')

    user_playlists = Playlist.objects.filter(user=request.user)
    if not user_playlists.exists():
        context = {
            'songs': [],
            'explained_songs': [],
            'algorithm': 'Personalized Hybrid Recommendations',
            'description': 'Direct recommendations blended from collaborative, content-based, and contextual signals',
            'user_playlists': user_playlists,
            'recommendation_type': 'hybrid',
            'subscription': subscription,
            'user_profile': None,
            'algorithm_weights': None,
            'no_playlist_recommendation_guard': True,
            'empty_recommendation_message': (
                'You have no playlists. Search songs or create a playlist to get recommendations.'
            ),
        }
        return render(request, 'main/recommendations.html', context)

    hybrid_result = HybridRecommendationEngine.get_hybrid_recommendations(request.user, limit=15)
    recommended_songs = [item['song'] for item in hybrid_result['recommendations']]

    explained_songs = []
    for item in hybrid_result['recommendations']:
        explained_songs.append({
            'song': item['song'],
            'reason': RecommendationExplainer.get_explanation(item) or 'Personalized for your listening taste',
            'confidence': 'High' if item['total_score'] >= 0.5 else 'Medium',
            'scores': {
                'total': round(item['total_score'], 3),
                'collaborative': round(item['collaborative_score'], 3),
                'content': round(item['content_score'], 3),
                'contextual': round(item['contextual_score'], 3),
            },
        })

    context = {
        'songs': recommended_songs,
        'explained_songs': explained_songs,
        'algorithm': 'Personalized Hybrid Recommendations',
        'description': 'Direct recommendations blended from collaborative, content-based, and contextual signals',
        'user_playlists': user_playlists,
        'recommendation_type': 'hybrid',
        'subscription': subscription,
        'user_profile': hybrid_result['profile'],
        'algorithm_weights': hybrid_result['weights'],
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
    subscription = Subscription.objects.get_or_create(user=request.user)[0]

    if not subscription.can_use_advanced_recommendations():
        return JsonResponse({
            'status': 'error',
            'message': 'Advanced recommendations require an active premium subscription.'
        }, status=403)

    has_playlists = Playlist.objects.filter(user=request.user).exists()
    has_playlist_songs = Song.objects.filter(playlists__user=request.user).exists()

    if not has_playlists:
        return JsonResponse({
            'status': 'success',
            'method': method,
            'count': 0,
            'songs': [],
            'message': 'No playlists found. Search songs or create a playlist to get recommendations.'
        })

    if method == 'collaborative' and not has_playlist_songs:
        return JsonResponse({
            'status': 'success',
            'method': method,
            'count': 0,
            'songs': [],
            'message': 'Collaborative recommendations need songs in your playlists first.'
        })
    
    try:
        if method == 'collaborative':
            songs = CollaborativeFiltering.recommend_for_user(
                request.user,
                limit=limit,
                fallback_to_content=False,
            )
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
    """Display user subscription status and all active subscription plans."""
    subscription = Subscription.objects.get_or_create(user=request.user)[0]
    available_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price', 'duration_days', 'name')
    current_plan = subscription.plan
    checkout_plan = available_plans.filter(tier='premium').first() or available_plans.first()
    premium_price = checkout_plan.price if checkout_plan else settings.SUBSCRIPTION_PRICE_NPR
    premium_duration_days = checkout_plan.duration_days if checkout_plan else settings.SUBSCRIPTION_DURATION_DAYS
    has_profile_email = bool((request.user.email or '').strip())
    
    context = {
        'subscription': subscription,
        'is_premium': subscription.is_premium(),
        'song_limit': subscription.get_playlist_song_limit(),
        'available_plans': available_plans,
        'current_plan': current_plan,
        'khalti_public_key': settings.KHALTI_PUBLIC_KEY,
        'khalti_mode': settings.KHALTI_MODE,
        'premium_price': premium_price,
        'premium_duration_days': premium_duration_days,
        'checkout_plan': checkout_plan,
        'has_profile_email': has_profile_email,
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


def _send_subscription_receipt_email(user, amount_npr, duration_days, expiry_date, reference):
    """Send a subscription receipt email when a payment is verified."""
    recipient = (user.email or '').strip()
    if not recipient:
        return False

    subject = 'Finder Premium Subscription Receipt'
    message = (
        f"Hello {user.get_full_name() or user.username},\n\n"
        f"Your premium subscription payment has been received successfully.\n"
        f"Amount: NPR {amount_npr}\n"
        f"Duration: {duration_days} days\n"
        f"Valid until: {expiry_date.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        f"Payment reference: {reference}\n\n"
        "Thank you for subscribing to Finder."
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [recipient],
        fail_silently=False,
    )
    return True


@login_required
def subscribe_premium(request):
    """Start Khalti payment for the premium subscription."""
    if request.method == 'POST':
        try:
            user_email = (request.user.email or '').strip()
            customer_email = user_email or f'{request.user.username}@example.com'

            plan_id = request.POST.get('plan_id')
            selected_plan = None
            if plan_id:
                selected_plan = SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first()
            if selected_plan is None:
                selected_plan = SubscriptionPlan.objects.filter(tier='premium', is_active=True).order_by('price').first()
            if selected_plan is None:
                selected_plan = SubscriptionPlan.objects.filter(is_active=True).order_by('price', 'duration_days', 'name').first()

            if selected_plan is None:
                messages.error(request, 'No active subscription plans are available right now.')
                return redirect('subscription_page')

            duration_days = int(selected_plan.duration_days) if selected_plan else int(settings.SUBSCRIPTION_DURATION_DAYS)
            price_npr = selected_plan.price if selected_plan else settings.SUBSCRIPTION_PRICE_NPR

            if not settings.KHALTI_SECRET_KEY:
                messages.error(request, 'Khalti secret key is not configured.')
                return redirect('subscription_page')

            amount_paisa = int(price_npr * 100)

            purchase_order_id = f'sub-{request.user.id}-{selected_plan.tier}-{uuid.uuid4().hex[:10]}'

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
                'purchase_order_name': f'{selected_plan.name if selected_plan else "Premium"} Subscription ({duration_days} days)',
                'customer_info': {
                    'name': request.user.get_full_name() or request.user.username,
                    'email': customer_email,
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
                'price_npr': str(price_npr),
                'selected_plan_id': selected_plan.id if selected_plan else None,
            }

            pending_payment = PaymentRecord.objects.create(
                user=request.user,
                plan=selected_plan,
                amount=price_npr,
                currency='NPR',
                provider='khalti',
                provider_reference=pidx,
                status='pending',
                notes='Payment initiated from subscription page.',
                raw_response=response_data,
            )
            request.session['khalti_subscription_meta']['pending_payment_id'] = pending_payment.id

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'ok',
                    'payment_url': payment_url,
                    'pidx': pidx,
                })

            return redirect(payment_url)
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': str(e),
                }, status=400)
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

        meta = request.session.pop('khalti_subscription_meta', {})
        payment_record = None
        pending_payment_id = meta.get('pending_payment_id')
        if pending_payment_id:
            payment_record = PaymentRecord.objects.filter(id=pending_payment_id, user=request.user).first()
        if payment_record is None:
            payment_record = PaymentRecord.objects.filter(
                user=request.user,
                provider='khalti',
                provider_reference=pidx,
            ).order_by('-created_at').first()

        if lookup_data.get('status') != 'Completed':
            if payment_record:
                payment_record.status = 'failed'
                payment_record.notes = f"Verification status: {lookup_data.get('status', 'Unknown')}"
                payment_record.raw_response = lookup_data
                payment_record.save(update_fields=['status', 'notes', 'raw_response'])
            else:
                PaymentRecord.objects.create(
                    user=request.user,
                    amount=0,
                    currency='NPR',
                    provider='khalti',
                    provider_reference=pidx,
                    status='failed',
                    notes=f"Verification status: {lookup_data.get('status', 'Unknown')}",
                    raw_response=lookup_data,
                )
            messages.warning(
                request,
                f"Khalti verification status: {lookup_data.get('status', 'Unknown')}. Premium was not activated.",
            )
            return redirect('subscription_page')

        selected_plan = None
        selected_plan_id = meta.get('selected_plan_id')
        if selected_plan_id:
            selected_plan = SubscriptionPlan.objects.filter(id=selected_plan_id).first()
        if selected_plan is None and payment_record and payment_record.plan_id:
            selected_plan = payment_record.plan

        duration_days = int(
            selected_plan.duration_days
            if selected_plan
            else meta.get('duration_days', settings.SUBSCRIPTION_DURATION_DAYS)
        )
        price_npr_raw = selected_plan.price if selected_plan else meta.get('price_npr', settings.SUBSCRIPTION_PRICE_NPR)
        price_npr = Decimal(str(price_npr_raw))

        subscription = Subscription.objects.get_or_create(user=request.user)[0]
        previous_tier = subscription.tier
        previous_plan = subscription.plan
        subscription.tier = 'premium'
        subscription.is_active = True
        subscription.expiry_date = timezone.now() + timedelta(days=duration_days)
        subscription.plan = selected_plan

        subscription.save()

        if payment_record:
            payment_record.plan = selected_plan
            payment_record.amount = price_npr
            payment_record.currency = 'NPR'
            payment_record.status = 'completed'
            payment_record.notes = 'Subscription payment verified via callback.'
            payment_record.raw_response = lookup_data
            payment_record.provider_reference = pidx
            payment_record.save(
                update_fields=['plan', 'amount', 'currency', 'status', 'notes', 'raw_response', 'provider_reference']
            )
        else:
            PaymentRecord.objects.create(
                user=request.user,
                amount=price_npr,
                currency='NPR',
                provider='khalti',
                provider_reference=pidx,
                status='completed',
                notes='Subscription payment verified via callback.',
                raw_response=lookup_data,
            )

        _log_subscription_change(
            user=request.user,
            previous_tier=previous_tier,
            new_tier=subscription.tier,
            previous_plan=previous_plan,
            new_plan=subscription.plan,
            source='user_purchase',
            notes=f'Khalti payment confirmed with reference {pidx}.',
            changed_by=request.user,
        )

        try:
            _send_subscription_receipt_email(
                user=request.user,
                amount_npr=price_npr,
                duration_days=duration_days,
                expiry_date=subscription.expiry_date,
                reference=pidx,
            )
        except Exception:
            messages.warning(request, 'Premium activated, but receipt email could not be sent.')

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
            previous_tier = subscription.tier
            previous_plan = subscription.plan
            subscription.cancel_subscription()

            _log_subscription_change(
                user=request.user,
                previous_tier=previous_tier,
                new_tier=subscription.tier,
                previous_plan=previous_plan,
                new_plan=subscription.plan,
                source='user_cancel',
                notes='User cancelled active subscription.',
                changed_by=request.user,
            )
            
            messages.warning(
                request,
                'Your Premium subscription has been cancelled. You now have access only to free features.',
            )
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
    playlist_limit = subscription.get_playlist_limit()
    has_playlist_capacity = playlists.count() < playlist_limit
    
    return render(request, "main/dashboard.html", {
        "playlists": playlists,
        "subscription": subscription,
        "is_premium": subscription.is_premium(),
        "playlist_limit": playlist_limit,
        "has_playlist_capacity": has_playlist_capacity,
    })


