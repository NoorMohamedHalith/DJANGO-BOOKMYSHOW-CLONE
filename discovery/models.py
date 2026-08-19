from django.db import models
from django.contrib.auth.models import User
from movies.models import Movie


class RecentlyViewed(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recently_viewed_movies')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='recent_views')
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-viewed_at']
        unique_together = ('user', 'movie')

    def __str__(self):
        return f"{self.user.username} viewed {self.movie.name} at {self.viewed_at}"
