from django.urls import path
from . import views

urlpatterns = [
    path('api/shows/<int:theater_id>/seats/', views.get_seats_api, name='get_seats_api'),
    path('api/reservations/create/', views.create_reservation_api, name='create_reservation_api'),
    path('api/reservations/<uuid:reservation_uuid>/modify/', views.modify_reservation_api, name='modify_reservation_api'),
    path('api/reservations/<uuid:reservation_uuid>/release/', views.release_reservation_api, name='release_reservation_api'),
    path('theater/<int:theater_id>/seats/', views.select_seats_view, name='select_seats_view'),
]
