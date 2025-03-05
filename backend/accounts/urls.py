from django.urls import path, include
from . import views

app_name = 'accounts'

# Template-based URLs
urlpatterns = [
    path('login/', views.LoginPageView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('stations/', include([
        path('', views.station_list, name='station_list'),
        path('create/', views.station_create, name='station_create'),
        path('<uuid:station_id>/', include([
            path('', views.station_detail, name='station_detail'),
            path('edit/', views.station_edit, name='station_edit'),
            path('delete/', views.station_delete, name='station_delete'),
            path('users/', views.station_user_list, name='station_user_list'),
            path('add-user/', views.station_add_user, name='station_add_user'),
            path('set-primary-contact/', views.set_primary_contact, name='set_primary_contact'),
        ])),
    ])),
    path('users/', include([
        path('', views.user_list, name='user_list'),
        path('create/staff/', views.create_staff_user, name='create_staff_user'),
        path('create/radio/', views.create_radio_user, name='create_radio_user'),
        path('<uuid:user_id>/', include([
            path('edit/', views.edit_user, name='edit_user'),
            path('delete/', views.delete_user, name='delete_user'),
            path('reset-password/', views.reset_password, name='reset_password'),
        ])),
    ])),
]