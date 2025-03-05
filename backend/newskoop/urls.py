from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),
    
    # Template-based root URL
    path('', lambda request: redirect('accounts:login'), name='home'),
    
    # Newsroom app URLs (template-based)
    path('newsroom/', include('newsroom.urls', namespace='newsroom')),
    
    # Accounts app template-based URLs
    path('accounts/', include('accounts.urls', namespace='accounts')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)