from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from movies.models import Movie, Booking


class MovieDetails(models.Model):
    AGE_CERTIFICATION_CHOICES = [
        ('U', 'U'),
        ('UA', 'UA'),
        ('A', 'A'),
    ]

    movie = models.OneToOneField(Movie, on_delete=models.CASCADE, related_name='details')
    age_certification = models.CharField(max_length=5, choices=AGE_CERTIFICATION_CHOICES, default='UA')
    duration_minutes = models.PositiveIntegerField(default=0)
    detailed_description = models.TextField(blank=True, default='')
    youtube_video_id = models.CharField(max_length=20, blank=True, default='')
    release_date = models.DateField(null=True, blank=True)

    def get_duration_display(self):
        if not self.duration_minutes:
            return "N/A"
        hours = self.duration_minutes // 60
        mins = self.duration_minutes % 60
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"

    def get_youtube_embed_url(self):
        if self.youtube_video_id:
            return f"https://www.youtube.com/embed/{self.youtube_video_id}"
        return ""

    def __str__(self):
        return f"Details for {self.movie.name}"


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Language(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class CastMember(models.Model):
    name = models.CharField(max_length=255)
    profile_image = models.ImageField(upload_to="cast/", blank=True, null=True)
    biography = models.TextField(blank=True, default='')

    def __str__(self):
        return self.name


class MovieGenre(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='movie_genres')
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE, related_name='movie_genres')

    class Meta:
        unique_together = ('movie', 'genre')

    def __str__(self):
        return f"{self.movie.name} - {self.genre.name}"


class MovieLanguage(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='movie_languages')
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='movie_languages')

    class Meta:
        unique_together = ('movie', 'language')

    def __str__(self):
        return f"{self.movie.name} - {self.language.name}"


class MovieCast(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='movie_casts')
    cast_member = models.ForeignKey(CastMember, on_delete=models.CASCADE, related_name='movie_casts')
    character_name = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        unique_together = ('movie', 'cast_member')

    def __str__(self):
        return f"{self.cast_member.name} as {self.character_name} in {self.movie.name}"


class MovieImage(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to="movie_gallery/")
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.movie.name}"


class Review(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='movie_reviews')
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review_text = models.TextField()
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('movie', 'user')

    def __str__(self):
        return f"Review by {self.user.username} for {self.movie.name} ({self.rating}/5)"


class ReviewReport(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('REVIEWED', 'Reviewed'),
        ('DISMISSED', 'Dismissed'),
    ]

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='reports')
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='review_reports')
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('review', 'reported_by')

    def __str__(self):
        return f"Report on review {self.review.id} by {self.reported_by.username}"
