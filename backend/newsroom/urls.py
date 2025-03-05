# newsroom/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'newsroom'

# Create a router for API views (for future use)
# router = DefaultRouter()
# router.register(r'stories', api_views.StoryViewSet)
# router.register(r'bulletins', api_views.BulletinViewSet)
# router.register(r'shows', api_views.ShowViewSet)
# router.register(r'categories', api_views.CategoryViewSet)
# router.register(r'tasks', api_views.TaskViewSet)

# Regular template-based URLs
urlpatterns = [
    # Dashboard
    path('', views.newsroom_dashboard, name='dashboard'),
    
    # Story urls
    path('stories/', views.story_list, name='story_list'),
    path('stories/create/', views.story_create, name='story_create'),
    path('stories/<uuid:story_id>/', views.story_detail, name='story_detail'),
    path('stories/<uuid:story_id>/edit/', views.story_edit, name='story_edit'),
    path('stories/<uuid:story_id>/publish/', views.story_publish, name='story_publish'),
    path('stories/<uuid:story_id>/upload-audio/', views.story_upload_audio, name='story_upload_audio'),
    path('stories/<uuid:story_id>/audio/<uuid:audio_id>/delete/', views.story_delete_audio, name='story_delete_audio'),
    path('stories/<uuid:story_id>/translate/', views.story_translate, name='story_translate'),
    
    # Bulletin urls
    path('bulletins/', views.bulletin_list, name='bulletin_list'),
    path('bulletins/create/', views.bulletin_create, name='bulletin_create'),
    path('bulletins/<uuid:bulletin_id>/', views.bulletin_detail, name='bulletin_detail'),
    path('bulletins/<uuid:bulletin_id>/edit/', views.bulletin_edit, name='bulletin_edit'),
    path('bulletins/<uuid:bulletin_id>/publish/', views.bulletin_publish, name='bulletin_publish'),
    path('bulletins/<uuid:bulletin_id>/translate/', views.bulletin_translate, name='bulletin_translate'),
    
    # Show urls
    path('shows/', views.show_list, name='show_list'),
    path('shows/create/', views.show_create, name='show_create'),
    path('shows/<uuid:show_id>/', views.show_detail, name='show_detail'),
    path('shows/<uuid:show_id>/edit/', views.show_edit, name='show_edit'),
    path('shows/<uuid:show_id>/publish/', views.show_publish, name='show_publish'),
    
    # Category urls
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<uuid:category_id>/edit/', views.category_edit, name='category_edit'),
    path('categories/<uuid:category_id>/delete/', views.category_delete, name='category_delete'),
    
    # Task urls
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/my/', views.my_tasks, name='my_tasks'),
    path('tasks/create/', views.task_create, name='task_create'),
    path('tasks/<uuid:task_id>/', views.task_detail, name='task_detail'),
    path('tasks/<uuid:task_id>/update-status/', views.task_update_status, name='task_update_status'),
    path('tasks/<uuid:task_id>/add-note/', views.add_task_note, name='add_task_note'),
    
    # Translation urls
    path('translation/', views.translation_dashboard, name='translation_dashboard'),
    path('translation/create-task/', views.create_translation_task, name='create_translation_task'),
    
    # API endpoints - commented out for now, will be added later
    # path('api/', include(router.urls)),
]