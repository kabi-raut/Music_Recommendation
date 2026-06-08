from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .models import AdminActionLog, PaymentRecord, Playlist, Subscription, SubscriptionChangeLog, SubscriptionPlan, SearchHistory, Song, SongLike, ListeningHistory
from .views import (
    ADMIN_PORTAL_USERNAME,
    _finalize_payment_record,
    _log_admin_action,
    _log_subscription_change,
    _retry_khalti_payment_lookup,
)


def admin_portal(request):
    """Custom admin operations page with a simple hardcoded login."""
    is_admin_authenticated = request.session.get('ops_admin_authenticated', False)

    if not is_admin_authenticated:
        return redirect('login')

    user_search = (request.GET.get('user_search') or '').strip()
    user_status_filter = (request.GET.get('user_status') or 'all').strip().lower()
    user_tier_filter = (request.GET.get('user_tier') or 'all').strip().lower()
    user_sort = (request.GET.get('user_sort') or 'joined_desc').strip().lower()
    user_page = request.GET.get('user_page', '1')
    active_tab = (request.GET.get('tab') or 'analytics').strip().lower()
    if active_tab not in {'analytics', 'users', 'plans', 'searches', 'billing', 'audit'}:
        active_tab = 'analytics'

    billing_status_filter = (request.GET.get('billing_status') or 'all').strip().lower()
    billing_provider_filter = (request.GET.get('billing_provider') or 'all').strip().lower()
    billing_user_search = (request.GET.get('billing_user') or '').strip()
    billing_date_from = (request.GET.get('billing_date_from') or '').strip()
    billing_date_to = (request.GET.get('billing_date_to') or '').strip()

    allowed_sorts = {
        'username_asc': 'username',
        'username_desc': '-username',
        'email_asc': 'email',
        'email_desc': '-email',
        'status_asc': 'is_active',
        'status_desc': '-is_active',
        'tier_asc': 'subscription__tier',
        'tier_desc': '-subscription__tier',
        'playlists_asc': 'playlist_count',
        'playlists_desc': '-playlist_count',
        'joined_asc': 'date_joined',
        'joined_desc': '-date_joined',
    }
    selected_sort = allowed_sorts.get(user_sort, '-date_joined')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'logout':
            request.session.pop('ops_admin_authenticated', None)
            return redirect('login')

        elif action == 'bulk_user_update':
            selected_user_ids = request.POST.getlist('selected_user_ids')
            bulk_action = (request.POST.get('bulk_action') or '').strip().lower()
            plan_id = request.POST.get('plan_id')

            if not selected_user_ids:
                messages.warning(request, 'Select at least one user to apply bulk actions.')
                return redirect('admin_portal')

            target_users = User.objects.filter(id__in=selected_user_ids, is_superuser=False)
            updated_count = 0

            if bulk_action == 'activate_users':
                updated_count = target_users.update(is_active=True)
                messages.success(request, f'Activated {updated_count} user(s).')

            elif bulk_action == 'deactivate_users':
                updated_count = target_users.update(is_active=False)
                messages.success(request, f'Deactivated {updated_count} user(s).')

            elif bulk_action in {'set_free', 'set_paid'}:
                selected_plan = SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first() if plan_id else None
                for user_item in target_users:
                    subscription, _ = Subscription.objects.get_or_create(user=user_item)
                    previous_tier = subscription.tier
                    previous_plan = subscription.plan

                    if bulk_action == 'set_paid':
                        subscription.tier = 'premium'
                        subscription.is_active = True
                        if selected_plan:
                            subscription.plan = selected_plan
                        if not subscription.expiry_date or subscription.expiry_date <= timezone.now():
                            subscription.expiry_date = timezone.now() + timedelta(days=30)
                    else:
                        subscription.tier = 'free'
                        subscription.is_active = True
                        subscription.expiry_date = None
                        subscription.plan = SubscriptionPlan.objects.filter(tier='free').first()

                    subscription.save()
                    _log_subscription_change(
                        user=user_item,
                        previous_tier=previous_tier,
                        new_tier=subscription.tier,
                        previous_plan=previous_plan,
                        new_plan=subscription.plan,
                        source='admin_update',
                        notes='Bulk update from custom admin portal.',
                    )
                    updated_count += 1

                if bulk_action == 'set_paid':
                    messages.success(request, f'Moved {updated_count} user(s) to paid tier.')
                else:
                    messages.success(request, f'Moved {updated_count} user(s) to free tier.')

            else:
                messages.warning(request, 'Please choose a valid bulk action.')

            return redirect('admin_portal')

        elif action == 'delete_user':
            user_id = request.POST.get('user_id')
            target_user = get_object_or_404(User, id=user_id)

            if target_user.is_superuser:
                messages.warning(request, 'Superuser accounts cannot be deleted here.')
            else:
                username = target_user.username
                target_user.delete()
                _log_admin_action(request.user, 'delete_user', 'user', username, 'User permanently deleted from custom admin portal.')
                messages.success(request, f'User "{username}" has been permanently deleted.')

            return redirect('admin_portal')

        elif action == 'toggle_user_status':
            user_id = request.POST.get('user_id')
            target_user = get_object_or_404(User, id=user_id)

            if target_user.is_superuser:
                messages.warning(request, 'Superuser accounts cannot be suspended here.')
            else:
                target_user.is_active = not target_user.is_active
                target_user.save(update_fields=['is_active'])
                status_label = 'activated' if target_user.is_active else 'suspended'
                _log_admin_action(request.user, 'toggle_user_status', 'user', target_user.username, f'User {status_label} from custom admin portal.')
                messages.success(request, f'User "{target_user.username}" has been {status_label}.')

            return redirect('admin_portal')

        elif action == 'set_subscription':
            user_id = request.POST.get('user_id')
            tier = (request.POST.get('tier') or 'free').strip().lower()
            plan_id = request.POST.get('plan_id')
            target_user = get_object_or_404(User, id=user_id)
            subscription, _ = Subscription.objects.get_or_create(user=target_user)
            previous_tier = subscription.tier
            previous_plan = subscription.plan

            if subscription.tier == tier and subscription.is_active:
                messages.info(request, f'User "{target_user.username}" is already on the {tier} tier.')
            else:
                if tier == 'premium':
                    subscription.tier = 'premium'
                    subscription.is_active = True
                    if plan_id:
                        selected_plan = SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first()
                        if selected_plan:
                            subscription.plan = selected_plan
                    if not subscription.expiry_date or subscription.expiry_date <= timezone.now():
                        subscription.expiry_date = timezone.now() + timedelta(days=30)
                else:
                    subscription.tier = 'free'
                    subscription.is_active = True
                    subscription.expiry_date = None
                    subscription.plan = SubscriptionPlan.objects.filter(tier='free').first()

                subscription.save()
                _log_subscription_change(
                    user=target_user,
                    previous_tier=previous_tier,
                    new_tier=subscription.tier,
                    previous_plan=previous_plan,
                    new_plan=subscription.plan,
                    source='admin_update',
                    notes='Updated from custom admin portal.',
                )
                _log_admin_action(
                    request.user,
                    'set_subscription',
                    'user',
                    target_user.username,
                    f'Subscription updated to {subscription.tier} via admin portal.',
                )
                messages.success(request, f'Subscription for "{target_user.username}" updated to {subscription.tier}.')

            return redirect('admin_portal')

        elif action == 'assign_subscription_plan':
            user_id = request.POST.get('user_id')
            plan_id = request.POST.get('plan_id')

            target_user = get_object_or_404(User, id=user_id)
            selected_plan = get_object_or_404(SubscriptionPlan, id=plan_id)
            subscription, _ = Subscription.objects.get_or_create(user=target_user)

            previous_tier = subscription.tier
            previous_plan = subscription.plan

            if selected_plan.tier == 'free':
                subscription.tier = 'free'
                subscription.is_active = True
                subscription.plan = selected_plan
                subscription.expiry_date = None
            else:
                subscription.tier = 'premium'
                subscription.is_active = True
                subscription.plan = selected_plan
                duration_days = selected_plan.duration_days or 30
                subscription.expiry_date = timezone.now() + timedelta(days=duration_days)

            subscription.save()

            _log_subscription_change(
                user=target_user,
                previous_tier=previous_tier,
                new_tier=subscription.tier,
                previous_plan=previous_plan,
                new_plan=subscription.plan,
                source='admin_update',
                notes='Subscription plan assigned from custom admin portal.',
            )
            _log_admin_action(
                request.user,
                'assign_subscription_plan',
                'user',
                target_user.username,
                f'Assigned {selected_plan.name} plan ({selected_plan.tier}) from admin portal.',
            )
            messages.success(request, f'Assigned plan "{selected_plan.name}" to {target_user.username}.')
            return redirect(f"{reverse('admin_portal')}?tab=users")

        elif action == 'create_subscription_plan':
            name = (request.POST.get('name') or '').strip()
            tier = (request.POST.get('tier') or '').strip().lower()
            price = (request.POST.get('price') or '0').strip()
            duration_days = (request.POST.get('duration_days') or '30').strip()
            max_playlists = (request.POST.get('max_playlists') or '3').strip()
            max_songs_per_playlist = (request.POST.get('max_songs_per_playlist') or '5').strip()
            description = (request.POST.get('description') or '').strip()
            features = (request.POST.get('features') or '').strip()
            is_active = (request.POST.get('is_active') or '1') == '1'
            ad_free = (request.POST.get('ad_free') or '0') == '1'
            download_available = (request.POST.get('download_available') or '0') == '1'
            offline_mode = (request.POST.get('offline_mode') or '0') == '1'
            hd_audio = (request.POST.get('hd_audio') or '0') == '1'

            if not name or not tier:
                messages.warning(request, 'Name and tier are required to create a subscription plan.')
                return redirect(f"{reverse('admin_portal')}?tab=plans")

            try:
                plan = SubscriptionPlan.objects.create(
                    name=name,
                    tier=tier,
                    price=price,
                    duration_days=int(duration_days),
                    description=description,
                    features=features,
                    max_playlists=int(max_playlists),
                    max_songs_per_playlist=int(max_songs_per_playlist),
                    ad_free=ad_free,
                    download_available=download_available,
                    offline_mode=offline_mode,
                    hd_audio=hd_audio,
                    is_active=is_active,
                )
                _log_admin_action(
                    request.user,
                    'create_subscription_plan',
                    'subscription_plan',
                    plan.name,
                    f'Created subscription plan {plan.name} ({plan.tier}).',
                )
                messages.success(request, f'Subscription plan "{plan.name}" created successfully.')
            except ValueError:
                messages.error(request, 'Could not create plan. Please check numeric values (price, duration, limits).')

            return redirect(f"{reverse('admin_portal')}?tab=plans")

        elif action == 'edit_subscription_plan':
            plan_id = request.POST.get('plan_id')
            plan = get_object_or_404(SubscriptionPlan, id=plan_id)

            name = (request.POST.get('name') or plan.name).strip()
            tier = (request.POST.get('tier') or plan.tier).strip().lower()
            price = (request.POST.get('price') or str(plan.price)).strip()
            duration_days = (request.POST.get('duration_days') or str(plan.duration_days)).strip()
            max_playlists = (request.POST.get('max_playlists') or str(plan.max_playlists)).strip()
            max_songs_per_playlist = (request.POST.get('max_songs_per_playlist') or str(plan.max_songs_per_playlist)).strip()
            description = (request.POST.get('description') or '').strip()
            features = (request.POST.get('features') or '').strip()
            is_active = (request.POST.get('is_active') or '1') == '1'
            ad_free = (request.POST.get('ad_free') or '0') == '1'
            download_available = (request.POST.get('download_available') or '0') == '1'
            offline_mode = (request.POST.get('offline_mode') or '0') == '1'
            hd_audio = (request.POST.get('hd_audio') or '0') == '1'

            try:
                plan.name = name
                plan.tier = tier
                plan.price = price
                plan.duration_days = int(duration_days)
                plan.max_playlists = int(max_playlists)
                plan.max_songs_per_playlist = int(max_songs_per_playlist)
                plan.description = description
                plan.features = features
                plan.is_active = is_active
                plan.ad_free = ad_free
                plan.download_available = download_available
                plan.offline_mode = offline_mode
                plan.hd_audio = hd_audio
                plan.save()

                _log_admin_action(
                    request.user,
                    'edit_subscription_plan',
                    'subscription_plan',
                    plan.name,
                    f'Updated subscription plan {plan.name} ({plan.tier}).',
                )
                messages.success(request, f'Subscription plan "{plan.name}" updated successfully.')
            except ValueError:
                messages.error(request, 'Invalid numeric values while updating the plan.')

            return redirect(f"{reverse('admin_portal')}?tab=plans")

        elif action == 'mark_payment_paid':
            payment_id = request.POST.get('payment_id')
            payment_record = get_object_or_404(PaymentRecord, id=payment_id)
            _finalize_payment_record(payment_record, source='admin_manual_mark_paid', status='completed')
            _log_admin_action(
                request.user,
                'mark_payment_paid',
                'payment',
                payment_record.provider_reference or f'Payment #{payment_record.id}',
                f'Payment marked paid manually for {payment_record.user.username}.',
            )
            messages.success(request, f'Payment #{payment_record.id} marked as paid.')
            return redirect(f"{reverse('admin_portal')}?tab=billing")

        elif action == 'retry_payment_webhook':
            payment_id = request.POST.get('payment_id')
            payment_record = get_object_or_404(PaymentRecord, id=payment_id)
            success, retry_message = _retry_khalti_payment_lookup(payment_record)
            _log_admin_action(
                request.user,
                'retry_payment_webhook',
                'payment',
                payment_record.provider_reference or f'Payment #{payment_record.id}',
                retry_message,
            )
            if success:
                messages.success(request, retry_message)
            else:
                messages.warning(request, retry_message)
            return redirect(f"{reverse('admin_portal')}?tab=billing")

        elif action == 'bulk_payment_action':
            selected_payment_ids = request.POST.getlist('selected_payment_ids')
            payment_bulk_action = (request.POST.get('payment_bulk_action') or '').strip().lower()

            if not selected_payment_ids:
                messages.warning(request, 'Select at least one payment record to run a bulk action.')
                return redirect(f"{reverse('admin_portal')}?tab=billing")

            payment_records = PaymentRecord.objects.filter(id__in=selected_payment_ids)
            if not payment_records.exists():
                messages.warning(request, 'No matching payment records were found for the selected items.')
                return redirect(f"{reverse('admin_portal')}?tab=billing")

            processed_count = 0
            success_count = 0

            if payment_bulk_action == 'mark_paid':
                for payment_record in payment_records:
                    _finalize_payment_record(payment_record, source='admin_bulk_mark_paid', status='completed')
                    _log_admin_action(
                        request.user,
                        'bulk_mark_payment_paid',
                        'payment',
                        payment_record.provider_reference or f'Payment #{payment_record.id}',
                        f'Payment marked paid in bulk for {payment_record.user.username}.',
                    )
                    processed_count += 1
                    success_count += 1
                messages.success(request, f'Marked {success_count} payment(s) as paid.')

            elif payment_bulk_action == 'retry_lookup':
                for payment_record in payment_records:
                    success, retry_message = _retry_khalti_payment_lookup(payment_record)
                    _log_admin_action(
                        request.user,
                        'bulk_retry_payment_webhook',
                        'payment',
                        payment_record.provider_reference or f'Payment #{payment_record.id}',
                        retry_message,
                    )
                    processed_count += 1
                    if success:
                        success_count += 1

                if success_count:
                    messages.success(request, f'{success_count} out of {processed_count} payment lookup retries succeeded.')
                else:
                    messages.warning(request, 'No selected payments were confirmed after retry.')
            else:
                messages.warning(request, 'Choose a valid bulk payment action before running.')

            return redirect(f"{reverse('admin_portal')}?tab=billing")

    filtered_payments = PaymentRecord.objects.select_related('user', 'plan').order_by('-created_at')
    if billing_status_filter in {'pending', 'completed', 'failed'}:
        filtered_payments = filtered_payments.filter(status=billing_status_filter)

    if billing_provider_filter != 'all':
        filtered_payments = filtered_payments.filter(provider__iexact=billing_provider_filter)

    if billing_user_search:
        filtered_payments = filtered_payments.filter(
            Q(user__username__icontains=billing_user_search) | Q(user__email__icontains=billing_user_search)
        )

    parsed_from_date = None
    if billing_date_from:
        try:
            parsed_from_date = datetime.strptime(billing_date_from, '%Y-%m-%d').date()
            filtered_payments = filtered_payments.filter(created_at__date__gte=parsed_from_date)
        except ValueError:
            messages.warning(request, 'Invalid billing start date. Use YYYY-MM-DD format.')

    parsed_to_date = None
    if billing_date_to:
        try:
            parsed_to_date = datetime.strptime(billing_date_to, '%Y-%m-%d').date()
            filtered_payments = filtered_payments.filter(created_at__date__lte=parsed_to_date)
        except ValueError:
            messages.warning(request, 'Invalid billing end date. Use YYYY-MM-DD format.')

    users = User.objects.annotate(
        playlist_count=Count('playlist', distinct=True),
        song_count=Count('playlist__songs', distinct=True),
    ).filter(is_superuser=False)

    if user_search:
        users = users.filter(
            Q(username__icontains=user_search) | Q(email__icontains=user_search)
        )

    if user_status_filter == 'active':
        users = users.filter(is_active=True)
    elif user_status_filter == 'inactive':
        users = users.filter(is_active=False)

    if user_tier_filter == 'premium':
        users = users.filter(subscription__tier=user_tier_filter)
    elif user_tier_filter == 'free':
        users = users.filter(Q(subscription__tier='free') | Q(subscription__isnull=True))

    users = users.order_by(selected_sort, 'id')
    user_paginator = Paginator(users, 12)
    user_page_obj = user_paginator.get_page(user_page)

    subscriptions = {
        subscription.user_id: subscription
        for subscription in Subscription.objects.select_related('plan').filter(user_id__in=[u.id for u in user_page_obj.object_list])
    }
    users_with_subscription = [
        {
            'user': user,
            'subscription': subscriptions.get(user.id),
        }
        for user in user_page_obj.object_list
    ]

    def build_user_detail_payload(user_item, user_subscription):
        user_playlists = list(
            Playlist.objects.filter(user=user_item)
            .annotate(song_count=Count('songs'))
            .order_by('-created_at')
            .values('id', 'name', 'is_public', 'is_auto_generated', 'song_count', 'created_at')[:5]
        )
        user_payments = list(
            PaymentRecord.objects.filter(user=user_item)
            .select_related('plan')
            .order_by('-created_at')
            .values('id', 'status', 'amount', 'currency', 'provider', 'provider_reference', 'created_at')[:5]
        )
        user_changes = list(
            SubscriptionChangeLog.objects.filter(user=user_item)
            .select_related('previous_plan', 'new_plan', 'changed_by')
            .order_by('-created_at')
            .values('id', 'previous_tier', 'new_tier', 'source', 'notes', 'created_at', 'changed_by__username')[:5]
        )
        return {
            'id': user_item.id,
            'username': user_item.username,
            'full_name': user_item.get_full_name() or '-',
            'email': user_item.email or '-',
            'is_active': user_item.is_active,
            'is_superuser': user_item.is_superuser,
            'date_joined': user_item.date_joined.strftime('%b %d, %Y %H:%M') if user_item.date_joined else '-',
            'last_login': user_item.last_login.strftime('%b %d, %Y %H:%M') if user_item.last_login else 'Never',
            'subscription_tier': user_subscription.tier if user_subscription else 'free',
            'subscription_plan': user_subscription.plan.name if user_subscription and user_subscription.plan else '-',
            'subscription_expiry': user_subscription.expiry_date.strftime('%b %d, %Y %H:%M') if user_subscription and user_subscription.expiry_date else '-',
            'playlists': [
                {
                    'id': playlist['id'],
                    'name': playlist['name'],
                    'is_public': playlist['is_public'],
                    'is_auto_generated': playlist['is_auto_generated'],
                    'song_count': playlist['song_count'],
                    'created_at': playlist['created_at'].strftime('%b %d, %Y %H:%M') if playlist['created_at'] else '-',
                }
                for playlist in user_playlists
            ],
            'payments': [
                {
                    'id': payment['id'],
                    'status': payment['status'],
                    'amount': str(payment['amount']),
                    'currency': payment['currency'],
                    'provider': payment['provider'],
                    'provider_reference': payment['provider_reference'] or '-',
                    'created_at': payment['created_at'].strftime('%b %d, %Y %H:%M') if payment['created_at'] else '-',
                }
                for payment in user_payments
            ],
            'subscription_changes': [
                {
                    'id': change['id'],
                    'previous_tier': change['previous_tier'] or 'none',
                    'new_tier': change['new_tier'],
                    'source': change['source'],
                    'notes': change['notes'] or '-',
                    'created_at': change['created_at'].strftime('%b %d, %Y %H:%M') if change['created_at'] else '-',
                    'changed_by': change['changed_by__username'] or 'system',
                }
                for change in user_changes
            ],
        }

    user_detail_payload = [
        build_user_detail_payload(user_item, subscriptions.get(user_item.id))
        for user_item in user_page_obj.object_list
    ]

    subscription_plans = SubscriptionPlan.objects.order_by('price')
    recent_payments = filtered_payments[:100]
    payment_provider_options = list(
        PaymentRecord.objects.exclude(provider__isnull=True).exclude(provider='')
        .values_list('provider', flat=True)
        .distinct()
        .order_by('provider')
    )
    plan_changes_qs = SubscriptionChangeLog.objects.select_related(
        'user', 'previous_plan', 'new_plan', 'changed_by'
    ).order_by('-created_at')

    if billing_user_search:
        plan_changes_qs = plan_changes_qs.filter(
            Q(user__username__icontains=billing_user_search) | Q(user__email__icontains=billing_user_search)
        )

    if parsed_from_date:
        plan_changes_qs = plan_changes_qs.filter(created_at__date__gte=parsed_from_date)
    if parsed_to_date:
        plan_changes_qs = plan_changes_qs.filter(created_at__date__lte=parsed_to_date)

    recent_plan_changes = plan_changes_qs[:30]
    recent_admin_actions = AdminActionLog.objects.select_related('actor').order_by('-created_at')[:30]

    # ===== ANALYTICS DATA =====
    total_users = User.objects.filter(is_superuser=False).count()
    active_users = User.objects.filter(is_superuser=False, is_active=True).count()
    premium_users = Subscription.objects.filter(tier='premium', is_active=True).count()
    free_users = total_users - premium_users
    
    # User growth (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    new_users_last_7_days = User.objects.filter(
        is_superuser=False, 
        date_joined__gte=seven_days_ago
    ).count()
    
    # Total unique songs used in playlists
    total_songs = Song.objects.filter(playlists__isnull=False).distinct().count()
    total_playlists = Playlist.objects.count()
    
    # Revenue this month
    this_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    revenue_this_month = PaymentRecord.objects.filter(
        status='completed',
        created_at__gte=this_month
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Top searched queries
    top_searches = SearchHistory.objects.values('query').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Recent searches
    recent_searches = SearchHistory.objects.select_related('user').order_by('-searched_at')[:50]
    
    # Most popular songs (by play count)
    top_songs = Song.objects.order_by('-play_count', '-like_count')[:10]
    
    # Most active users (by playlist count)
    top_users = User.objects.annotate(
        playlist_count=Count('playlist'),
        song_count=Count('playlist__songs', distinct=True)
    ).filter(is_superuser=False).order_by('-playlist_count', '-song_count')[:10]

    top_user_ids = [user.id for user in top_users if user.id not in {entry['id'] for entry in user_detail_payload}]
    if top_user_ids:
        top_user_subscriptions = {
            subscription.user_id: subscription
            for subscription in Subscription.objects.select_related('plan').filter(user_id__in=top_user_ids)
        }
        user_detail_payload.extend(
            build_user_detail_payload(user_item, top_user_subscriptions.get(user_item.id))
            for user_item in top_users
            if user_item.id in top_user_ids
        )

    context = {
        'is_admin_authenticated': is_admin_authenticated,
        'users_with_subscription': users_with_subscription,
        'user_page_obj': user_page_obj,
        'user_search': user_search,
        'user_status_filter': user_status_filter,
        'user_tier_filter': user_tier_filter,
        'user_sort': user_sort,
        'active_tab': active_tab,
        'subscription_plans': subscription_plans,
        'recent_payments': recent_payments,
        'billing_total_count': filtered_payments.count(),
        'billing_status_filter': billing_status_filter,
        'billing_provider_filter': billing_provider_filter,
        'billing_user_search': billing_user_search,
        'billing_date_from': billing_date_from,
        'billing_date_to': billing_date_to,
        'payment_provider_options': payment_provider_options,
        'recent_plan_changes': recent_plan_changes,
        'recent_admin_actions': recent_admin_actions,
        'user_detail_payload': user_detail_payload,
        # Analytics data
        'total_users': total_users,
        'active_users': active_users,
        'premium_users': premium_users,
        'free_users': free_users,
        'new_users_last_7_days': new_users_last_7_days,
        'total_songs': total_songs,
        'total_playlists': total_playlists,
        'revenue_this_month': revenue_this_month,
        'top_searches': top_searches,
        'recent_searches': recent_searches,
        'top_songs': top_songs,
        'top_users': top_users,
    }
    return render(request, 'main/admin_portal.html', context)
