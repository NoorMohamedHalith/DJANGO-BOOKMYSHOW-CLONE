from django.urls import path
from . import views

urlpatterns = [
    path('admin-dashboard/', views.dashboard_view, name='admin_dashboard'),
    path('api/analytics/kpis/', views.api_kpi_summary, name='api_kpi_summary'),
    path('api/analytics/revenue/', views.api_revenue_timeline, name='api_revenue_timeline'),
    path('api/analytics/top-movies/', views.api_top_movies, name='api_top_movies'),
    path('api/analytics/theater-occupancy/', views.api_theater_occupancy, name='api_theater_occupancy'),
    path('api/analytics/user-growth/', views.api_user_growth, name='api_user_growth'),
    path('api/analytics/export-csv/', views.export_csv_report_view, name='export_csv_report'),
]
