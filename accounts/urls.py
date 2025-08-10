from django.urls import path
from .views import (
    profile_view,
    home
)

urlpatterns = [
    path('', home, name='home'),
    path('profile/', profile_view, name='profile'),
]
