from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone

from movies.models import Movie, Theater, Seat, Booking
from movie_features.models import Genre, Language, MovieGenre, MovieLanguage
from discovery.models import RecentlyViewed
from discovery.services import MovieDiscoveryService


class DiscoveryTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(username='discuser', password='password123')

        self.genre_scifi = Genre.objects.create(name='Sci-Fi')
        self.genre_action = Genre.objects.create(name='Action')

        self.lang_english = Language.objects.create(name='English')

        self.movie1 = Movie.objects.create(
            name='Matrix Reloaded',
            image='movies/matrix.jpg',
            rating=4.7,
            cast='Keanu Reeves',
            description='Cyberpunk action sci-fi'
        )
        self.movie2 = Movie.objects.create(
            name='Avatar: The Way of Water',
            image='movies/avatar.jpg',
            rating=4.9,
            cast='Sam Worthington',
            description='Epic sci-fi adventure'
        )
        self.movie3 = Movie.objects.create(
            name='The Dark Knight',
            image='movies/batman.jpg',
            rating=4.9,
            cast='Christian Bale',
            description='Superhero action crime'
        )

        MovieGenre.objects.create(movie=self.movie1, genre=self.genre_scifi)
        MovieGenre.objects.create(movie=self.movie2, genre=self.genre_scifi)
        MovieGenre.objects.create(movie=self.movie3, genre=self.genre_action)

        MovieLanguage.objects.create(movie=self.movie1, language=self.lang_english)
        MovieLanguage.objects.create(movie=self.movie2, language=self.lang_english)

        self.theater = Theater.objects.create(name='Screen 1', movie=self.movie1, time=timezone.now() + timedelta(hours=2))
        self.seat = Seat.objects.create(theater=self.theater, seat_number='D1', is_booked=True)
        self.booking = Booking.objects.create(user=self.user, seat=self.seat, movie=self.movie1, theater=self.theater)

    # 1. Search movies by query
    def test_search_movies_returns_matching_results(self):
        base_qs = MovieDiscoveryService.get_base_queryset()
        res = MovieDiscoveryService.search_movies(base_qs, 'Matrix')
        self.assertEqual(res.count(), 1)
        self.assertEqual(res.first(), self.movie1)

    # 2. Filter movies by genre & min rating
    def test_filter_movies_by_genre_and_min_rating(self):
        base_qs = MovieDiscoveryService.get_base_queryset()
        filtered = MovieDiscoveryService.filter_movies(base_qs, {'genre_id': self.genre_scifi.id, 'min_rating': 4.8})
        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first(), self.movie2)

    # 3. Sort movies by popularity and rating
    def test_sort_movies(self):
        base_qs = MovieDiscoveryService.get_base_queryset()
        sorted_pop = MovieDiscoveryService.sort_movies(base_qs, 'popularity')
        self.assertEqual(sorted_pop.first(), self.movie1)  # has 1 booking

    # 4. Personalized recommendations based on booking history
    def test_personalized_recommendations(self):
        recs = MovieDiscoveryService.get_recommended_movies(self.user, limit=6)
        self.assertTrue(len(recs) >= 1)
        # Should recommend movie2 (Avatar) because it shares Sci-Fi genre with booked movie1 (Matrix)
        self.assertIn(self.movie2, recs)

    # 5. Recommendation fallback for new user
    def test_recommendation_fallback_for_new_user(self):
        new_user = User.objects.create_user(username='newbie', password='password123')
        recs = MovieDiscoveryService.get_recommended_movies(new_user, limit=6)
        self.assertTrue(len(recs) >= 3)

    # 6. AJAX API discovery endpoint returns valid JSON
    def test_api_discover_movies_endpoint(self):
        response = self.client.get('/api/discover/movies/?q=Matrix')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['total_count'], 1)
        self.assertEqual(data['movies'][0]['name'], 'Matrix Reloaded')

    # 7. Recently viewed recording
    def test_record_recently_viewed(self):
        recent = MovieDiscoveryService.record_recently_viewed(self.user, self.movie2)
        self.assertIsNotNone(recent)
        self.assertEqual(RecentlyViewed.objects.filter(user=self.user, movie=self.movie2).count(), 1)

    # 8. Custom login view renders tabbed User vs Admin UI
    def test_custom_login_view_renders_tabbed_ui(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'User Login')
        self.assertContains(response, 'Admin Login')

    # 9. Regular user login redirects to discover page
    def test_regular_user_login_redirection(self):
        response = self.client.post('/login/', {'username': 'discuser', 'password': 'password123'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/movies/discover/', response.url)

    # 10. Staff user login redirects to admin dashboard
    def test_staff_user_admin_login_redirection(self):
        staff = User.objects.create_superuser(username='staffadmin', password='password123')
        response = self.client.post('/login/', {'username': 'staffadmin', 'password': 'password123', 'is_admin_login': 'true'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin-dashboard/', response.url)

