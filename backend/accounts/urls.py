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

# API endpoints
api_urlpatterns = [
    # User endpoints
    path('login/', views.LoginView.as_view(), name='api_login'),
    path('logout/', views.LogoutView.as_view(), name='api_logout'),
    path('profile/', views.UserProfileView.as_view(), name='api_profile'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Admin endpoints
    path('admin/', include(admin_router.urls)),
    
    # Radio station endpoints
    path('radio/', include(radio_router.urls)),
]

# Template-based routes with 'accounts/' prefix
template_urlpatterns = [
    # Authentication and dashboard
    path('', views.dashboard_view, name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('accounts/login/', views.LoginPageView.as_view(), name='login'),  # Updated
    path('accounts/logout/', views.logout_view, name='logout'),  # Updated
    path('accounts/profile/', views.profile_view, name='profile'),  # Updated
    
    # User management
    path('accounts/users/', views.user_list, name='user_list'),  # Updated
    path('accounts/users/staff/create/', views.create_staff_user, name='create_staff_user'),  # Updated
    path('accounts/users/radio/create/', views.create_radio_user, name='create_radio_user'),  # Updated
    path('accounts/users/<uuid:user_id>/edit/', views.edit_user, name='edit_user'),  # Updated
    path('accounts/users/<uuid:user_id>/delete/', views.delete_user, name='delete_user'),  # Updated
    path('accounts/users/<uuid:user_id>/reset-password/', views.reset_password, name='reset_password'),  # Updated
    
    # Radio station management
    path('accounts/stations/', views.station_list, name='station_list'),  # Updated
    path('accounts/stations/create/', views.station_create, name='station_create'),  # Updated
    path('accounts/stations/<uuid:station_id>/', views.station_detail, name='station_detail'),  # Updated
    path('accounts/stations/<uuid:station_id>/edit/', views.station_edit, name='station_edit'),  # Updated
    path('accounts/stations/<uuid:station_id>/delete/', views.station_delete, name='station_delete'),  # Updated
    path('accounts/stations/<uuid:station_id>/users/', views.station_user_list, name='station_user_list'),  # Updated
    path('accounts/stations/<uuid:station_id>/users/add/', views.station_add_user, name='station_add_user'),  # Updated
    path('accounts/stations/<uuid:station_id>/users/<uuid:user_id>/set-primary/', views.set_primary_contact, name='set_primary_contact'),  # Updated
]

# Only include API endpoints directly in the app's urls
urlpatterns = api_urlpatterns