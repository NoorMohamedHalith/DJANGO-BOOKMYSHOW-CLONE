from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from movies.models import Movie, Theater, Seat, Booking
from movie_features.models import (
    MovieDetails, Genre, Language, CastMember,
    MovieGenre, MovieLanguage, MovieCast, Review, ReviewReport
)
from movie_features.services import ReviewEligibilityService, extract_youtube_id, get_movie_details_context


class MovieFeaturesTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Users
        self.user1 = User.objects.create_user(username='user1', password='password123')
        self.user2 = User.objects.create_user(username='user2', password='password123')

        # Movies
        self.movie1 = Movie.objects.create(
            name='Inception',
            image='movies/inception.jpg',
            rating=4.8,
            cast='Leonardo DiCaprio',
            description='Mind bending thriller'
        )
        self.movie2 = Movie.objects.create(
            name='Interstellar',
            image='movies/interstellar.jpg',
            rating=4.7,
            cast='Matthew McConaughey',
            description='Space exploration'
        )
        self.movie3 = Movie.objects.create(
            name='The Notebook',
            image='movies/notebook.jpg',
            rating=4.0,
            cast='Ryan Gosling',
            description='Romantic drama'
        )

        # Movie Details
        self.details1 = MovieDetails.objects.create(
            movie=self.movie1,
            age_certification='UA',
            duration_minutes=148,
            detailed_description='A thief who steals corporate secrets through the use of dream-sharing technology.',
            youtube_video_id='YoHD9XEInc0',
            release_date=timezone.now().date() - timedelta(days=30)
        )
        self.details2 = MovieDetails.objects.create(
            movie=self.movie2,
            age_certification='U',
            duration_minutes=169,
            detailed_description='A team of explorers travel through a wormhole in space.',
            youtube_video_id='zSWdZVtXT7E',
            release_date=timezone.now().date() - timedelta(days=10)
        )

        # Genres & Languages
        self.action_genre = Genre.objects.create(name='Action', active=True)
        self.sci_fi_genre = Genre.objects.create(name='Sci-Fi', active=True)
        self.romance_genre = Genre.objects.create(name='Romance', active=True)

        self.english_lang = Language.objects.create(name='English')

        MovieGenre.objects.create(movie=self.movie1, genre=self.action_genre)
        MovieGenre.objects.create(movie=self.movie1, genre=self.sci_fi_genre)
        MovieGenre.objects.create(movie=self.movie2, genre=self.sci_fi_genre)
        MovieGenre.objects.create(movie=self.movie3, genre=self.romance_genre)

        MovieLanguage.objects.create(movie=self.movie1, language=self.english_lang)
        MovieLanguage.objects.create(movie=self.movie2, language=self.english_lang)

        # Past Theater & Booking for User1 on Movie1
        self.past_theater = Theater.objects.create(
            name='PVR Cinema Past',
            movie=self.movie1,
            time=timezone.now() - timedelta(hours=5)
        )
        self.seat1 = Seat.objects.create(theater=self.past_theater, seat_number='A1', is_booked=True)
        self.booking1 = Booking.objects.create(
            user=self.user1,
            seat=self.seat1,
            movie=self.movie1,
            theater=self.past_theater
        )

        # Future Theater & Booking for User2 on Movie1
        self.future_theater = Theater.objects.create(
            name='PVR Cinema Future',
            movie=self.movie1,
            time=timezone.now() + timedelta(days=2)
        )
        self.seat2 = Seat.objects.create(theater=self.future_theater, seat_number='A2', is_booked=True)
        self.booking2 = Booking.objects.create(
            user=self.user2,
            seat=self.seat2,
            movie=self.movie1,
            theater=self.future_theater
        )

    # 1. YouTube video ID extraction and validation
    def test_youtube_video_id_extraction(self):
        url1 = "https://www.youtube.com/watch?v=YoHD9XEInc0"
        url2 = "https://youtu.be/YoHD9XEInc0"
        url3 = "https://www.youtube.com/embed/YoHD9XEInc0"
        raw_id = "YoHD9XEInc0"
        invalid_url = "https://example.com/invalid"

        self.assertEqual(extract_youtube_id(url1), "YoHD9XEInc0")
        self.assertEqual(extract_youtube_id(url2), "YoHD9XEInc0")
        self.assertEqual(extract_youtube_id(url3), "YoHD9XEInc0")
        self.assertEqual(extract_youtube_id(raw_id), "YoHD9XEInc0")
        self.assertIsNone(extract_youtube_id(invalid_url))

    # 2. Review eligibility — user with valid completed booking can review
    def test_review_eligibility_completed_booking(self):
        can_review = ReviewEligibilityService.can_user_review(self.user1, self.movie1)
        self.assertTrue(can_review)

    # 3. Review eligibility — user without booking cannot review
    def test_review_eligibility_no_booking(self):
        can_review = ReviewEligibilityService.can_user_review(self.user2, self.movie2)
        self.assertFalse(can_review)

    # 4. Review eligibility — user with future showtime cannot review
    def test_review_eligibility_future_booking(self):
        # User2 has a booking for movie1, but the showtime is in the future
        can_review = ReviewEligibilityService.can_user_review(self.user2, self.movie1)
        self.assertFalse(can_review)

    # 5. Average rating calculation using Avg()
    def test_average_rating_calculation(self):
        Review.objects.create(
            movie=self.movie1,
            user=self.user1,
            booking=self.booking1,
            rating=5,
            review_text='Masterpiece!',
            is_verified=True
        )
        Review.objects.create(
            movie=self.movie1,
            user=self.user2,
            rating=3,
            review_text='Good movie.',
            is_verified=False
        )
        context = get_movie_details_context(self.movie1)
        self.assertEqual(context['avg_rating'], 4.0)
        self.assertEqual(context['review_count'], 2)

    # 6. Verified Viewer badge is set correctly based on booking
    def test_verified_viewer_badge(self):
        self.client.login(username='user1', password='password123')
        response = self.client.post(f'/movie/{self.movie1.id}/review/add/', {
            'rating': 5,
            'review_text': 'Great movie experience!'
        })
        self.assertEqual(response.status_code, 302)
        
        review = Review.objects.get(movie=self.movie1, user=self.user1)
        self.assertTrue(review.is_verified)
        self.assertEqual(review.booking, self.booking1)

    # 7. User cannot edit another user's review
    def test_user_cannot_edit_other_user_review(self):
        review = Review.objects.create(
            movie=self.movie1,
            user=self.user1,
            booking=self.booking1,
            rating=5,
            review_text='Original review by user1',
            is_verified=True
        )

        # Login as user2 and attempt to edit user1's review
        self.client.login(username='user2', password='password123')
        response = self.client.post(f'/review/{review.id}/edit/', {
            'rating': 1,
            'review_text': 'Hacked review text'
        })
        self.assertEqual(response.status_code, 403)

        # Refresh review from database and check untouched
        review.refresh_from_db()
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.review_text, 'Original review by user1')

    # 8. User cannot report the same review twice
    def test_user_cannot_report_review_twice(self):
        review = Review.objects.create(
            movie=self.movie1,
            user=self.user1,
            booking=self.booking1,
            rating=5,
            review_text='Great film',
            is_verified=True
        )

        self.client.login(username='user2', password='password123')
        
        # First report
        response1 = self.client.post(f'/review/{review.id}/report/', {'reason': 'Spam content'})
        self.assertEqual(response1.status_code, 302)
        self.assertEqual(ReviewReport.objects.filter(review=review, reported_by=self.user2).count(), 1)

        # Second report attempt
        response2 = self.client.post(f'/review/{review.id}/report/', {'reason': 'Duplicate report'})
        self.assertEqual(response2.status_code, 302)
        self.assertEqual(ReviewReport.objects.filter(review=review, reported_by=self.user2).count(), 1)

    # 9. Similar movies query returns correct movies (genre/language match)
    def test_similar_movies_query(self):
        context = get_movie_details_context(self.movie1)
        similar_movies = list(context['similar_movies'])
        
        # movie2 shares Sci-Fi genre and English language with movie1
        self.assertIn(self.movie2, similar_movies)
        # movie3 has Romance genre (no match with movie1)
        self.assertNotIn(self.movie3, similar_movies)
        # movie1 should be excluded from its own similar list
        self.assertNotIn(self.movie1, similar_movies)

    # 10. Trending movies query returns correct order (based on bookings)
    def test_trending_movies_query(self):
        # movie1 has 2 bookings (booking1 and booking2)
        # movie2 has 0 bookings
        context = get_movie_details_context(self.movie1)
        trending_movies = list(context['trending_movies'])
        
        self.assertGreaterEqual(len(trending_movies), 2)
        self.assertEqual(trending_movies[0], self.movie1)
