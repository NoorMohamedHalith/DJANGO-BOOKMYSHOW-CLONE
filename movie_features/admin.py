from django.contrib import admin
from .models import (
    MovieDetails, Genre, Language, CastMember,
    MovieGenre, MovieLanguage, MovieCast, MovieImage,
    Review, ReviewReport
)
from .services import extract_youtube_id


class MovieImageInline(admin.TabularInline):
    model = MovieImage
    extra = 1


class MovieCastInline(admin.TabularInline):
    model = MovieCast
    extra = 1


class MovieGenreInline(admin.TabularInline):
    model = MovieGenre
    extra = 1


class MovieLanguageInline(admin.TabularInline):
    model = MovieLanguage
    extra = 1


@admin.register(MovieDetails)
class MovieDetailsAdmin(admin.ModelAdmin):
    list_display = ('movie', 'age_certification', 'duration_minutes', 'release_date', 'youtube_video_id')
    search_fields = ('movie__name', 'detailed_description', 'youtube_video_id')
    list_filter = ('age_certification', 'release_date')

    def save_model(self, request, obj, form, change):
        if obj.youtube_video_id:
            extracted_id = extract_youtube_id(obj.youtube_video_id)
            if extracted_id:
                obj.youtube_video_id = extracted_id
        super().save_model(request, obj, form, change)


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('name', 'active')
    list_filter = ('active',)
    search_fields = ('name',)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(CastMember)
class CastMemberAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name', 'biography')


@admin.register(MovieGenre)
class MovieGenreAdmin(admin.ModelAdmin):
    list_display = ('movie', 'genre')
    list_filter = ('genre',)
    search_fields = ('movie__name', 'genre__name')


@admin.register(MovieLanguage)
class MovieLanguageAdmin(admin.ModelAdmin):
    list_display = ('movie', 'language')
    list_filter = ('language',)
    search_fields = ('movie__name', 'language__name')


@admin.register(MovieCast)
class MovieCastAdmin(admin.ModelAdmin):
    list_display = ('movie', 'cast_member', 'character_name')
    search_fields = ('movie__name', 'cast_member__name', 'character_name')


@admin.register(MovieImage)
class MovieImageAdmin(admin.ModelAdmin):
    list_display = ('movie', 'is_primary', 'uploaded_at')
    list_filter = ('is_primary', 'uploaded_at')
    search_fields = ('movie__name',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('movie', 'user', 'rating', 'is_verified', 'created_at')
    list_filter = ('rating', 'is_verified', 'created_at')
    search_fields = ('movie__name', 'user__username', 'review_text')


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = ('review', 'reported_by', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('review__movie__name', 'reported_by__username', 'reason')
