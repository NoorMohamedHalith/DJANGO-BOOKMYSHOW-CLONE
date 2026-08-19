from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('discovery.urls')),
    path('users/', include('users.urls')),
    path('', include('users.urls')),
    path('movies/', include('movies.urls')),
    path('features/', include('movie_features.urls')),
    path('', include('movie_features.urls')),
    path('', include('seat_reservations.urls')),
    path('payments/', include('booking_payments.urls')),
    path('', include('booking_payments.urls')),
    path('', include('payments.urls')),
    path('', include('analytics.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
