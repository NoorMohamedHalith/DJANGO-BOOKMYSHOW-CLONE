import re
from django.utils import timezone
from django.db.models import Avg, Count, Q
from movies.models import Movie, Booking
from .models import MovieDetails, MovieImage, MovieGenre, MovieLanguage, MovieCast, Review


class ReviewEligibilityService:
    @staticmethod
    def get_eligible_booking(user, movie):
        """
        Returns a completed/past booking for the given user and movie if showtime has passed.
        """
        if not user or not user.is_authenticated:
            return None
        now = timezone.now()
        # Find booking where theater.time < current time
        return Booking.objects.filter(
            user=user,
            movie=movie,
            theater__time__lt=now
        ).order_by('-theater__time').first()

    @classmethod
    def can_user_review(cls, user, movie):
        """
        Returns True if the user has a confirmed booking for the movie whose showtime has passed.
        """
        return cls.get_eligible_booking(user, movie) is not None


def extract_youtube_id(url_or_id):
    """
    Extracts and validates YouTube 11-character video ID from a URL or raw ID string.
    Returns None if invalid.
    """
    if not url_or_id or not isinstance(url_or_id, str):
        return None
    url_or_id = url_or_id.strip()
    # Check if raw 11-char ID
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    
    # Regex patterns for standard YouTube URLs
    patterns = [
        r'(?:v=|\/embed\/|\/v\/|youtu\.be\/|\/shorts\/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return None


def get_movie_details_context(movie, user=None):
    """
    Builds and returns all extended movie feature context for a given movie.
    Uses select_related, prefetch_related, and database Avg() aggregation.
    """
    movie_details = MovieDetails.objects.filter(movie=movie).first()
    gallery_images = MovieImage.objects.filter(movie=movie).order_by('-is_primary', '-uploaded_at')
    movie_genres = MovieGenre.objects.filter(movie=movie, genre__active=True).select_related('genre')
    movie_languages = MovieLanguage.objects.filter(movie=movie).select_related('language')
    movie_casts = MovieCast.objects.filter(movie=movie).select_related('cast_member')

    # Aggregations using Django ORM Avg()
    reviews_qs = Review.objects.filter(movie=movie)
    avg_rating_dict = reviews_qs.aggregate(avg=Avg('rating'))
    avg_rating = avg_rating_dict['avg']
    if avg_rating is not None:
        avg_rating = round(float(avg_rating), 1)
    
    review_count = reviews_qs.count()
    reviews = reviews_qs.select_related('user', 'booking').order_by('-created_at')

    can_review = False
    user_review = None
    if user and user.is_authenticated:
        can_review = ReviewEligibilityService.can_user_review(user, movie)
        user_review = reviews_qs.filter(user=user).first()

    # Similar Movies: shared genres and languages, excluding current movie
    genre_ids = movie_genres.values_list('genre_id', flat=True)
    language_ids = movie_languages.values_list('language_id', flat=True)

    similar_movies = Movie.objects.filter(
        Q(movie_genres__genre_id__in=genre_ids) | Q(movie_languages__language_id__in=language_ids)
    ).exclude(id=movie.id).select_related('details').prefetch_related('movie_genres__genre', 'movie_languages__language').distinct()[:6]

    # Trending Movies: ordered by confirmed booking count
    trending_movies = Movie.objects.annotate(
        booking_count=Count('booking')
    ).order_by('-booking_count', '-id').select_related('details').prefetch_related('movie_genres__genre')[:6]

    # Recently Released Movies: sorted by release date
    recently_released_movies = Movie.objects.filter(
        details__release_date__isnull=False
    ).select_related('details').order_by('-details__release_date', '-id')[:6]

    return {
        'movie_details': movie_details,
        'gallery_images': gallery_images,
        'movie_genres': movie_genres,
        'movie_languages': movie_languages,
        'movie_casts': movie_casts,
        'avg_rating': avg_rating,
        'review_count': review_count,
        'reviews': reviews,
        'can_user_review': can_review,
        'user_review': user_review,
        'similar_movies': similar_movies,
        'trending_movies': trending_movies,
        'recently_released_movies': recently_released_movies,
    }
