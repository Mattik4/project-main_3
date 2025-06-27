from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
import re


class EmailAuthenticationForm(AuthenticationForm):
    """Custom login form that uses email instead of username"""
    
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Adres email',
            'autofocus': True
        })
    )
    
    password = forms.CharField(
        label='Hasło',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Hasło'
        })
    )
    
    def clean_username(self):
        email = self.cleaned_data.get('username')
        
        # Find user by email
        try:
            user = User.objects.get(email=email)
            return user.username  # Return username for authentication
        except User.DoesNotExist:
            raise ValidationError('Nie znaleziono użytkownika z tym adresem email.')
    
    def confirm_login_allowed(self, user):
        """Additional checks for user login"""
        super().confirm_login_allowed(user)
        
        # Check if user profile is active
        if hasattr(user, 'profile') and not user.profile.aktywny:
            raise ValidationError('Twoje konto zostało dezaktywowane. Skontaktuj się z administratorem.')


class CustomPasswordChangeForm(PasswordChangeForm):
    """Enhanced password change form with comprehensive validation"""
    
    def __init__(self, *args, **kwargs):
        # Extract request if provided
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        self.fields['old_password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Aktualne hasło'
        })
        
        self.fields['new_password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Nowe hasło'
        })
        
        self.fields['new_password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Potwierdź nowe hasło'
        })
        
        # Add help text
        self.fields['new_password1'].help_text = (
            "Hasło musi zawierać co najmniej 8 znaków, w tym wielkie i małe litery, cyfry oraz znaki specjalne."
        )
    
    def clean_old_password(self):
        """Validate the old password"""
        old_password = self.cleaned_data.get('old_password')
        
        if not self.user.check_password(old_password):
            raise ValidationError('Podane aktualne hasło jest nieprawidłowe.')
        
        return old_password
    
    def clean_new_password1(self):
        """Enhanced validation for new password"""
        old_password = self.cleaned_data.get('old_password')
        new_password1 = self.cleaned_data.get('new_password1')
        
        if not new_password1:
            raise ValidationError('To pole jest wymagane.')
        
        # Check if new password is the same as current password
        if old_password and new_password1:
            if self.user.check_password(new_password1):
                raise ValidationError(
                    '🚫 Nowe hasło nie może być takie samo jak obecne hasło. '
                    'Wybierz inne hasło dla bezpieczeństwa swojego konta.'
                )
        
        # Additional security checks
        user = self.user
        
        # Check if password contains user's personal information
        user_info = [
            user.username.lower(),
            user.first_name.lower(),
            user.last_name.lower(),
            user.email.split('@')[0].lower() if user.email else '',
        ]
        
        password_lower = new_password1.lower()
        for info in user_info:
            if info and len(info) > 2 and info in password_lower:
                raise ValidationError(
                    f'🚫 Hasło nie może zawierać Twoich danych osobowych ({info}).'
                )
        
        # Check for common weak patterns
        if self._is_weak_password(new_password1):
            raise ValidationError(
                '🚫 To hasło jest zbyt słabe. Unikaj prostych wzorców jak "123456", "qwerty", czy "password".'
            )
        
        # Check password strength
        if not self._is_strong_password(new_password1):
            raise ValidationError(
                '🚫 Hasło musi zawierać co najmniej: '
                '8 znaków, jedną wielką literę, jedną małą literę, jedną cyfrę i jeden znak specjalny.'
            )
        
        return new_password1
    
    def clean_new_password2(self):
        """Validate that both new passwords match"""
        new_password1 = self.cleaned_data.get('new_password1')
        new_password2 = self.cleaned_data.get('new_password2')
        
        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise ValidationError('🚫 Nowe hasła nie są zgodne.')
        
        return new_password2
    
    def _is_weak_password(self, password):
        """Check for common weak password patterns"""
        weak_patterns = [
            'password', 'hasło', '123456', 'qwerty', 'abc123', 
            'admin', 'user', 'test', 'guest', '111111', '000000',
            'asdfgh', 'zxcvbn', 'polonya', 'qazwsx', 'mnbvcx'
        ]
        
        password_lower = password.lower()
        
        # Check for exact matches or patterns
        for pattern in weak_patterns:
            if pattern in password_lower:
                return True
        
        # Check for keyboard patterns
        keyboard_patterns = ['qwert', 'asdf', 'zxcv', '12345', '54321']
        for pattern in keyboard_patterns:
            if pattern in password_lower:
                return True
        
        # Check for repeated characters (like "aaaa" or "1111")
        if re.search(r'(.)\1{3,}', password):
            return True
        
        return False
    
    def _is_strong_password(self, password):
        """Check if password meets strength requirements"""
        if len(password) < 8:
            return False
        
        # Must contain at least one lowercase letter
        if not re.search(r'[a-z]', password):
            return False
        
        # Must contain at least one uppercase letter
        if not re.search(r'[A-Z]', password):
            return False
        
        # Must contain at least one digit
        if not re.search(r'\d', password):
            return False
        
        # Must contain at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False
        
        return True
    
    def save(self, commit=True):
        """Save the new password and log the activity"""
        user = super().save(commit)
        
        if commit:
            # Log password change activity with real IP
            try:
                from documents.models import ActivityLog
                from django.utils import timezone
                
                # Get IP address from request if available
                ip_address = '127.0.0.1'
                if self.request:
                    x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
                    if x_forwarded_for:
                        ip_address = x_forwarded_for.split(',')[0]
                    else:
                        ip_address = self.request.META.get('REMOTE_ADDR', '127.0.0.1')
                
                ActivityLog.objects.create(
                    uzytkownik=user,
                    typ_aktywnosci='zmiana_hasla',
                    szczegoly=f'Użytkownik {user.get_full_name()} zmienił swoje hasło',
                    znacznik_czasu=timezone.now(),
                    adres_ip=ip_address
                )
            except ImportError:
                # ActivityLog model might not exist yet
                pass
            except Exception as e:
                # Don't fail password change if logging fails
                print(f"Failed to log password change: {e}")
        
        return user


# Note: All user management is now done through Django admin
# No need for custom user creation or profile edit forms