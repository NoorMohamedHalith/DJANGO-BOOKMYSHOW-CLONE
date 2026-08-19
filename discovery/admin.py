from django.contrib import admin
from .models import RecentlyViewed


@admin.register(RecentlyViewed)
class RecentlyViewedAdmin(admin.ModelAdmin):
    list_display = ('user', 'movie', 'viewed_at')
    list_filter = ('viewed_at',)
    search_fields = ('user__username', 'movie__name')
    readonly_fields = ('viewed_at',)
