from django.contrib import admin
from .models import User, Profile

# Register your models here.


class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'first_name', 'last_name', 'phone', 'is_organizer', 'is_approved', 'is_superuser', 'is_verified', 'is_staff', 'is_active', 'created_at', 'updated_at')
    list_filter = ('email', 'first_name', 'last_name', 'phone', 'is_organizer', 'is_approved', 'is_superuser', 'is_verified', 'is_staff', 'is_active', 'created_at', 'updated_at')
    search_fields = ('email', 'first_name', 'last_name', 'phone')


class ProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'bio', 'location', 'birth_date', 'profile_picture')
    list_filter = ('user', 'bio', 'location', 'birth_date', 'profile_picture')
    search_fields = ('user', 'bio', 'location', 'birth_date', 'profile_picture')


admin.site.register(User, UserAdmin)
admin.site.register(Profile, ProfileAdmin)
