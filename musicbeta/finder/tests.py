from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Genre, Playlist, Song, Subscription, UserPreference
from .recommendations import CollaborativeFiltering


@override_settings(
	KHALTI_SECRET_KEY='test_secret_key',
	KHALTI_PUBLIC_KEY='test_public_key',
	KHALTI_MODE='sandbox',
)
class KhaltiSubscriptionTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='tester',
			password='testpass123',
			email='tester@example.com',
		)
		self.client.login(username='tester', password='testpass123')

	@patch('finder.views._khalti_post_json')
	def test_subscribe_premium_redirects_to_khalti_payment_url(self, mock_khalti_post):
		mock_khalti_post.return_value = {
			'payment_url': 'https://sandbox-pay.khalti.com/test-link',
			'pidx': 'test-pidx-1',
		}

		response = self.client.post(reverse('subscribe_premium'), {'duration': 30})

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, 'https://sandbox-pay.khalti.com/test-link')
		self.assertEqual(mock_khalti_post.call_count, 1)

	@patch('finder.views._khalti_post_json')
	def test_khalti_callback_activates_premium_on_completed_status(self, mock_khalti_post):
		mock_khalti_post.return_value = {
			'status': 'Completed',
		}
		session = self.client.session
		session['khalti_subscription_meta'] = {
			'purchase_order_id': f'sub-{self.user.id}-30',
			'duration_days': 30,
		}
		session.save()

		response = self.client.get(
			reverse('khalti_subscription_callback'),
			{'pidx': 'test-pidx-2', 'status': 'Completed'},
		)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('subscription_page'))

		subscription = Subscription.objects.get(user=self.user)
		self.assertTrue(subscription.is_premium())

	@patch('finder.views._khalti_post_json')
	def test_khalti_callback_does_not_activate_premium_when_lookup_not_completed(self, mock_khalti_post):
		mock_khalti_post.return_value = {
			'status': 'Pending',
		}

		response = self.client.get(
			reverse('khalti_subscription_callback'),
			{'pidx': 'test-pidx-3', 'status': 'Completed'},
		)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('subscription_page'))

		subscription = Subscription.objects.get(user=self.user)
		self.assertFalse(subscription.is_premium())


class CollaborativeFilteringTests(TestCase):
	def setUp(self):
		self.target_user = User.objects.create_user(
			username='target',
			password='testpass123',
		)
		self.similar_user = User.objects.create_user(
			username='similar',
			password='testpass123',
		)
		self.noisy_user = User.objects.create_user(
			username='noisy',
			password='testpass123',
		)

		self.rock = Genre.objects.create(name='Rock')
		self.pop = Genre.objects.create(name='Pop')

		self.shared_song = Song.objects.create(title='Shared Song', artist='Artist A', genre=self.rock, source='jamendo')
		self.target_song = Song.objects.create(title='Target Song', artist='Artist B', genre=self.pop, source='jamendo')
		self.recommended_song = Song.objects.create(title='Recommended Song', artist='Artist C', genre=self.rock, source='jamendo')
		self.noisy_song_1 = Song.objects.create(title='Noisy Song 1', artist='Artist D', genre=self.rock, source='jamendo')
		self.noisy_song_2 = Song.objects.create(title='Noisy Song 2', artist='Artist E', genre=self.rock, source='jamendo')
		self.noisy_song_3 = Song.objects.create(title='Noisy Song 3', artist='Artist F', genre=self.rock, source='jamendo')

		target_playlist = Playlist.objects.create(user=self.target_user, name='Target Playlist', is_public=True)
		target_playlist.songs.add(self.shared_song, self.target_song)

		similar_playlist = Playlist.objects.create(user=self.similar_user, name='Similar Playlist', is_public=True)
		similar_playlist.songs.add(self.shared_song, self.recommended_song)

		noisy_playlist = Playlist.objects.create(user=self.noisy_user, name='Noisy Playlist', is_public=True)
		noisy_playlist.songs.add(self.noisy_song_1, self.noisy_song_2, self.noisy_song_3)

		noisy_preferences = UserPreference.objects.create(user=self.noisy_user)
		noisy_preferences.liked_genres.add(self.rock)

	def test_get_similar_users_prioritizes_shared_song_overlap(self):
		similar_users = list(CollaborativeFiltering.get_similar_users(self.target_user, limit=5))

		self.assertGreaterEqual(len(similar_users), 2)
		self.assertEqual(similar_users[0], self.similar_user)
		self.assertEqual(similar_users[1], self.noisy_user)
		self.assertEqual(similar_users[0].shared_song_count, 1)
		self.assertEqual(similar_users[1].shared_song_count, 0)

	def test_recommend_for_user_prefers_songs_from_strongest_overlap(self):
		recommended_songs = list(CollaborativeFiltering.recommend_for_user(self.target_user, limit=5))

		self.assertTrue(recommended_songs)
		self.assertEqual(recommended_songs[0], self.recommended_song)
		self.assertNotIn(self.target_song, recommended_songs)

	@patch('finder.recommendations.JamendoAPI.get_popular_tracks')
	def test_new_user_without_playlists_gets_jamendo_fallback(self, mock_get_popular_tracks):
		cold_start_user = User.objects.create_user(
			username='coldstart',
			password='testpass123',
		)

		mock_get_popular_tracks.return_value = [
			{
				'id': f'jamendo_{index}',
				'external_id': str(index),
				'title': f'Open Track {index}',
				'artist': f'Artist {index}',
				'genre': 'Ambient',
				'audio_url': f'https://example.com/{index}.mp3',
				'cover_image': '',
				'duration': 200 + index,
				'source': 'jamendo',
			}
			for index in range(1, 11)
		]

		recommended_songs = list(CollaborativeFiltering.recommend_for_user(cold_start_user, limit=10))

		self.assertEqual(mock_get_popular_tracks.call_count, 1)
		self.assertEqual(len(recommended_songs), 10)
		self.assertTrue(all(song.source == 'jamendo' for song in recommended_songs))


