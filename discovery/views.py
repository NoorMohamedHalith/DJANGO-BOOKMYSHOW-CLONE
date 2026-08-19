from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages

from movies.models import Movie, Theater
from movie_features.models import Genre, Language
from users.forms import UserRegisterForm
from .models import RecentlyViewed
from .services import MovieDiscoveryService


def signup_view(request):
    """
    Custom user registration view. On success, logs user in and redirects to discovery hub.
    """
    if request.user.is_authenticated:
        return redirect('discover_movies')

    if request.method == 'POST':
        form = UserRegisterForm(request.POST) if 'UserRegisterForm' in globals() else UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to BookMyShow, {user.username}! Your account has been created.")
            return redirect('discover_movies')
    else:
        form = UserRegisterForm() if 'UserRegisterForm' in globals() else UserCreationForm()

    return render(request, 'registration/signup.html', {'form': form})


def custom_login_view(request):
    """
    Custom login view with Tabbed User vs Admin authentication separation logic.
    Staff/Admin users redirect to /admin-dashboard/ or /admin/, regular users to discovery page.
    """
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard')
        return redirect('discover_movies')

    active_tab = request.GET.get('tab', 'user')

    if request.method == 'POST':
        is_admin_login = request.POST.get('is_admin_login') == 'true'
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")

            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)

            if user.is_staff or is_admin_login:
                return redirect('admin_dashboard')
            return redirect('discover_movies')
        else:
            active_tab = 'admin' if is_admin_login else 'user'
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = AuthenticationForm()

    context = {
        'form': form,
        'active_tab': active_tab
    }
    return render(request, 'registration/login.html', context)


def custom_logout_view(request):
    """
    Custom logout view redirecting to login page.
    """
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')


def discover_movies_view(request):
    """
    Main movie discovery view rendering search bar, filter sidebar, sort options, recommendations, and paginated movie grid.
    """
    query = request.GET.get('q', '').strip()
    genre_id = request.GET.get('genre')
    language_id = request.GET.get('language')
    theater_id = request.GET.get('theater')
    min_rating = request.GET.get('min_rating')
    sort_by = request.GET.get('sort', 'popularity')
    page_number = request.GET.get('page', 1)

    filters = {
        'genre_id': genre_id,
        'language_id': language_id,
        'theater_id': theater_id,
        'min_rating': min_rating,
    }

    base_qs = MovieDiscoveryService.get_base_queryset()
    searched_qs = MovieDiscoveryService.search_movies(base_qs, query)
    filtered_qs = MovieDiscoveryService.filter_movies(searched_qs, filters)
    sorted_qs = MovieDiscoveryService.sort_movies(filtered_qs, sort_by)

    paginator = Paginator(sorted_qs, 12)
    page_obj = paginator.get_page(page_number)

    genres = Genre.objects.all()
    languages = Language.objects.all()
    theaters = Theater.objects.all()
    recommended_movies = MovieDiscoveryService.get_recommended_movies(request.user, limit=6)

    recently_viewed = []
    if request.user.is_authenticated:
        recently_viewed = RecentlyViewed.objects.filter(user=request.user).select_related('movie')[:6]

    context = {
        'page_obj': page_obj,
        'movies': page_obj.object_list,
        'total_count': paginator.count,
        'genres': genres,
        'languages': languages,
        'theaters': theaters,
        'recommended_movies': recommended_movies,
        'recently_viewed': recently_viewed,
        'query': query,
        'selected_genre': int(genre_id) if genre_id and genre_id.isdigit() else None,
        'selected_language': int(language_id) if language_id and language_id.isdigit() else None,
        'selected_theater': int(theater_id) if theater_id and theater_id.isdigit() else None,
        'selected_min_rating': min_rating or '',
        'selected_sort': sort_by,
    }
    return render(request, 'discovery/discover.html', context)


def api_discover_movies(request):
    """
    AJAX API endpoint returning JSON formatted movie discovery data for dynamic page updates.
    """
    query = request.GET.get('q', '').strip()
    genre_id = request.GET.get('genre')
    language_id = request.GET.get('language')
    theater_id = request.GET.get('theater')
    min_rating = request.GET.get('min_rating')
    sort_by = request.GET.get('sort', 'popularity')
    page_number = request.GET.get('page', 1)

    filters = {
        'genre_id': genre_id,
        'language_id': language_id,
        'theater_id': theater_id,
        'min_rating': min_rating,
    }

    base_qs = MovieDiscoveryService.get_base_queryset()
    searched_qs = MovieDiscoveryService.search_movies(base_qs, query)
    filtered_qs = MovieDiscoveryService.filter_movies(searched_qs, filters)
    sorted_qs = MovieDiscoveryService.sort_movies(filtered_qs, sort_by)

    paginator = Paginator(sorted_qs, 12)
    page_obj = paginator.get_page(page_number)

    movies_data = []
    for m in page_obj.object_list:
        genres_list = [mg.genre.name for mg in m.movie_genres.all()]
        languages_list = [ml.language.name for ml in m.movie_languages.all()]
        image_url = m.poster_url if hasattr(m, 'poster_url') else (m.image.url if m.image else '/media/movies/avengers_endgame_real.jpg')

        movies_data.append({
            'id': m.id,
            'name': m.name,
            'image_url': image_url,
            'rating': float(m.avg_review_rating or m.rating),
            'cast': m.cast,
            'description': m.description,
            'genres': genres_list,
            'languages': languages_list,
            'booking_count': m.booking_count,
        })

    return JsonResponse({
        'success': True,
        'movies': movies_data,
        'total_count': paginator.count,
        'current_page': page_obj.number,
        'total_pages': paginator.num_pages,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
    })


def record_view_and_redirect(request, movie_id):
    """
    Records a movie view for recently viewed tracking and redirects to theater list.
    """
    movie = get_object_or_404(Movie, id=movie_id)
    if request.user.is_authenticated:
        MovieDiscoveryService.record_recently_viewed(request.user, movie)
    return redirect('theater_list', movie_id=movie.id)
