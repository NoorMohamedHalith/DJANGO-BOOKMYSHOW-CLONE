from django.urls import path
from . import views

urlpatterns = [
    path('movie/<int:movie_id>/review/add/', views.add_review, name='add_review'),
    path('review/<int:review_id>/edit/', views.edit_review, name='edit_review'),
    path('review/<int:review_id>/report/', views.report_review, name='report_review'),
]
