from django.contrib import admin

from .models import Reclamation, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "phone", "birth_date", "has_disability", "created_at")
	list_filter = ("has_disability", "created_at")
	search_fields = ("user__username", "user__email", "phone")


@admin.register(Reclamation)
class ReclamationAdmin(admin.ModelAdmin):
	list_display = ("name", "email", "category", "created_at")
	list_filter = ("category", "created_at")
	search_fields = ("name", "email", "message")
