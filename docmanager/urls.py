from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

# Funkcja obsługująca przekierowanie z głównej strony
def root_redirect_view(request):
    if request.user.is_authenticated:
        # Jeśli zalogowany, idź do dashboardu
        return redirect('documents:home')
    else:
        # Jeśli niezalogowany, idź do logowania
        return redirect('users:login')

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Nasze nowe, proste przekierowanie dla strony głównej '/'
    path('', root_redirect_view, name='root_redirect'),

    # Aplikacje dołączone pod swoimi prefiksami
    path('documents/', include('documents.urls')),
    path('users/', include('users.urls')),

    # Wbudowane widoki autoryzacji (fallback)
    path('accounts/', include('django.contrib.auth.urls')),
]

# Serwowanie plików w trybie deweloperskim
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)