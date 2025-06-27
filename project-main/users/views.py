from django.shortcuts import redirect
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.views import View
from django.utils import timezone
from .models import UserSession
from .forms import EmailAuthenticationForm, CustomPasswordChangeForm
from users.permissions import (
user_can_view_document, user_can_edit_document, user_can_delete_document,
user_can_create_document, user_can_comment_on_document, user_can_share_document,
user_can_view_folder, user_can_edit_folder, user_can_delete_folder,
user_can_create_folder)

class CustomLoginView(LoginView):
    """Custom login view with email authentication and session tracking"""
    form_class = EmailAuthenticationForm
    template_name = 'users/login.html'
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        print(f">>>>>> [2] KROK 2: WIDOK LOGOWANIA - Użytkownik jest zalogowany: {request.user.is_authenticated}")
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Track user session on successful login"""
        response = super().form_valid(form)
        
        # Create session record
        UserSession.objects.create(
            user=self.request.user,
            session_key=self.request.session.session_key,
            ip_address=self.get_client_ip(),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')[:500]
        )
        
        messages.success(
            self.request, 
            f'Witaj, {self.request.user.get_full_name() or self.request.user.email}!'
        )
        return response
    
    def get_client_ip(self):
        """Get client IP address"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    def get_success_url(self):
        """Redirect to intended page or dashboard"""
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse('documents:home')


class CustomLogoutView(LoginRequiredMixin, View):
    """Custom logout view with session cleanup"""
    
    def post(self, request):
        # Update session record
        try:
            session = UserSession.objects.get(
                user=request.user,
                session_key=request.session.session_key,
                is_active=True
            )
            session.logout_time = timezone.now()
            session.is_active = False
            session.save()
        except UserSession.DoesNotExist:
            pass
        
        logout(request)
        messages.info(request, 'Zostałeś wylogowany. Do zobaczenia!')
        return redirect('users:login')


class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """Custom password change view (optional feature)"""
    form_class = CustomPasswordChangeForm
    template_name = 'users/password_change.html'
    success_url = reverse_lazy('documents:home')
    
    def form_valid(self, form):
        messages.success(self.request, 'Hasło zostało zmienione pomyślnie.')
        return super().form_valid(form)
