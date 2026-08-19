from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.custom_login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.custom_logout_view, name='logout'),
    path('movies/discover/', views.discover_movies_view, name='discover_movies'),
    path('api/discover/movies/', views.api_discover_movies, name='api_discover_movies'),
    path('movies/<int:movie_id>/view/', views.record_view_and_redirect, name='record_view_and_redirect'),
]
