# accounts/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views
from . import admin_views

# Create a router for admin views
admin_router = DefaultRouter()
admin_router.register(r'users', admin_views.AdminUserViewSet)

# Create a router for radio station views
radio_router = DefaultRouter()
radio_router.register(r'stations', views.RadioStationViewSet)

app_name = 'accounts'

urlpatterns = [
    # User endpoints
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Admin endpoints
    path('admin/', include(admin_router.urls)),
    
    # Radio station endpoints
    path('radio/', include(radio_router.urls)),
]