from django.db import models
from django.db.models import Q, Count, Avg, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from movies.models import Movie, Booking, Theater
from movie_features.models import Genre, Language, MovieGenre, MovieLanguage, Review
from .models import RecentlyViewed


class MovieDiscoveryService:
    @classmethod
    def get_base_queryset(cls):
        """
        Returns optimized base Movie queryset with prefetched relationships & annotations.
        """
        return (
            Movie.objects.prefetch_related(
                'movie_genres__genre',
                'movie_languages__language',
                'theaters'
            )
            .annotate(
                booking_count=Count('booking', distinct=True),
                avg_review_rating=Coalesce(Avg('reviews__rating'), F('rating'), output_field=models.FloatField())
            )
        )

    @classmethod
    def search_movies(cls, queryset, query):
        """
        Full-text search on movie name, description, and cast using Q OR-expressions.
        """
        if not query:
            return queryset
        query = query.strip()
        return queryset.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(cast__icontains=query)
        ).distinct()

    @classmethod
    def filter_movies(cls, queryset, filters=None):
        """
        Applies multi-criteria filters (genre, language, theater, min_rating).
        """
        if not filters:
            return queryset

        genre_id = filters.get('genre_id')
        if genre_id:
            queryset = queryset.filter(movie_genres__genre_id=genre_id)

        language_id = filters.get('language_id')
        if language_id:
            queryset = queryset.filter(movie_languages__language_id=language_id)

        theater_id = filters.get('theater_id')
        if theater_id:
            queryset = queryset.filter(theaters__id=theater_id)

        min_rating = filters.get('min_rating')
        if min_rating:
            try:
                min_r = float(min_rating)
                queryset = queryset.filter(Q(rating__gte=min_r) | Q(avg_review_rating__gte=min_r))
            except ValueError:
                pass

        return queryset.distinct()

    @classmethod
    def sort_movies(cls, queryset, sort_by='popularity'):
        """
        Sorts movie queryset by popularity, rating, newest, or title.
        """
        if sort_by == 'popularity':
            return queryset.order_by('-booking_count', '-id')
        elif sort_by == 'rating':
            return queryset.order_by('-avg_review_rating', '-rating', '-id')
        elif sort_by == 'newest':
            return queryset.order_by('-id')
        elif sort_by == 'title':
            return queryset.order_by('name')
        else:
            return queryset.order_by('-booking_count', '-id')

    @classmethod
    def get_recommended_movies(cls, user=None, limit=6):
        """
        Personalised recommendation engine:
        1. Analyzes user booking history for preferred genres and languages.
        2. Recommends unbooked movies matching those genres/languages.
        3. Fallbacks to top-booked / highest-rated trending movies.
        """
        recommendations = []
        rec_ids = set()

        if user and user.is_authenticated:
            booked_movie_ids = list(Booking.objects.filter(user=user).values_list('movie_id', flat=True).distinct())

            if booked_movie_ids:
                user_genre_ids = list(MovieGenre.objects.filter(movie_id__in=booked_movie_ids).values_list('genre_id', flat=True).distinct())
                user_language_ids = list(MovieLanguage.objects.filter(movie_id__in=booked_movie_ids).values_list('language_id', flat=True).distinct())

                personalized_qs = cls.get_base_queryset().exclude(id__in=booked_movie_ids)
                
                cond = Q()
                if user_genre_ids:
                    cond |= Q(movie_genres__genre_id__in=user_genre_ids)
                if user_language_ids:
                    cond |= Q(movie_languages__language_id__in=user_language_ids)

                if cond:
                    matched_movies = list(personalized_qs.filter(cond).distinct()[:limit])
                    for m in matched_movies:
                        recommendations.append(m)
                        rec_ids.add(m.id)

        # Trending Fallback if fewer than limit recommendations found
        if len(recommendations) < limit:
            needed = limit - len(recommendations)
            fallback_qs = cls.get_base_queryset().exclude(id__in=rec_ids).order_by('-booking_count', '-rating')[:needed]
            for m in fallback_qs:
                recommendations.append(m)
                rec_ids.add(m.id)

        return recommendations[:limit]

    @classmethod
    def record_recently_viewed(cls, user, movie):
        """
        Records or updates a user's recently viewed movie.
        """
        if not user or not user.is_authenticated or not movie:
            return None

        recent, created = RecentlyViewed.objects.update_or_create(
            user=user,
            movie=movie,
            defaults={'viewed_at': timezone.now()}
        )
        return recent
