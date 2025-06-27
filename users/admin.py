from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from django.contrib import messages

from .models import Role, UserProfile, UserSession


class CustomUserCreationForm(BaseUserCreationForm):
    """Custom user creation form with role selection and required fields"""
    
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label='Imię',
        widget=forms.TextInput(attrs={'class': 'vTextField'})
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        label='Nazwisko',
        widget=forms.TextInput(attrs={'class': 'vTextField'})
    )
    email = forms.EmailField(
        required=True,
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'vTextField'})
    )
    rola = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=True,
        label='Rola',
        empty_label=None,
        widget=forms.Select(attrs={'class': 'vTextField'})
    )

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "rola")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default role to 'czytelnik' if it exists
        try:
            default_role = Role.objects.get(nazwa=Role.READER)
            self.fields['rola'].initial = default_role
        except Role.DoesNotExist:
            pass

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise ValidationError('Użytkownik z tym adresem email już istnieje.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        
        if commit:
            user.save()
            
            # Create UserProfile with selected role
            selected_role = self.cleaned_data.get("rola")
            if selected_role:
                UserProfile.objects.create(
                    user=user,
                    rola=selected_role,
                    aktywny=True
                )
        return user


class CustomUserChangeForm(forms.ModelForm):
    """Simplified user change form with role field."""
    
    rola = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=False,
        label='Rola',
        widget=forms.Select(attrs={'class': 'vTextField'})
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load current role from associated UserProfile
        if self.instance and self.instance.pk:
            try:
                profile = self.instance.profile
                self.fields['rola'].initial = profile.rola
            except UserProfile.DoesNotExist:
                # Create profile if it doesn't exist
                default_role, _ = Role.objects.get_or_create(
                    nazwa=Role.READER,
                    defaults={'opis': 'Podstawowe uprawnienia czytelnika'}
                )
                UserProfile.objects.create(
                    user=self.instance,
                    rola=default_role,
                    aktywny=True
                )
                self.fields['rola'].initial = default_role


class CustomUserAdmin(BaseUserAdmin):
    """Enhanced User Admin with role field."""
    
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    
    list_display = (
        'username', 'email', 'first_name', 'last_name', 
        'get_user_profile_role', 
        'is_staff', 'is_active',
        'date_joined', 'last_login'
    )
    list_filter = (
        'is_staff', 'is_active',
        'profile__rola',
        'date_joined'
    )
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)
    
    # Fieldsets for ADDING users
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('Dane personalne', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('Rola w systemie', {
            'fields': ('rola',)
        }),
    )
    
    # Fieldsets for EDITING users
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Rola', {'fields': ('rola',)}),
        ('Informacje osobowe', {'fields': ('first_name', 'last_name', 'email')}),
        ('Uprawnienia', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Ważne daty', {'fields': ('last_login', 'date_joined')}),
    )
    
    actions = ['make_admin_role', 'make_editor_role', 'make_reader_role']

    @admin.display(description='Rola (Profil)', ordering='profile__rola__nazwa')
    def get_user_profile_role(self, obj):
        """Get user role from UserProfile."""
        try:
            if obj.profile and obj.profile.rola:
                role_name = obj.profile.rola.get_nazwa_display()
                role_value = obj.profile.rola.nazwa
                if role_value == Role.ADMIN:
                    return format_html('<span style="color: #dc3545; font-weight: bold;">{}</span>', role_name)
                elif role_value == Role.EDITOR:
                    return format_html('<span style="color: #fd7e14; font-weight: bold;">{}</span>', role_name)
                elif role_value == Role.READER:
                    return format_html('<span style="color: #0dcaf0;">{}</span>', role_name)
                return role_name
        except UserProfile.DoesNotExist:
            pass
        return format_html('<span style="color: #6c757d;">Brak profilu/roli</span>')

    def get_queryset(self, request):
        """Optimize queries by prefetching related UserProfile and Role."""
        return super().get_queryset(request).select_related('profile__rola')
    
    def get_form(self, request, obj=None, **kwargs):
        """Ensure the rola field is properly handled."""
        form = super().get_form(request, obj, **kwargs)
        
        # Add rola field to form if it's not in add mode
        if obj and hasattr(form, 'base_fields') and 'rola' in form.base_fields:
            # Ensure the field gets the current value
            try:
                profile = obj.profile
                if profile and profile.rola:
                    form.base_fields['rola'].initial = profile.rola
            except UserProfile.DoesNotExist:
                pass
                
        return form
    
    def save_model(self, request, obj, form, change):
        """Save user and handle role from form."""
        super().save_model(request, obj, form, change)
        
        # Handle role from POST data directly
        if 'rola' in request.POST:
            rola_id = request.POST.get('rola')
            if rola_id:
                try:
                    rola = Role.objects.get(id=rola_id)
                    
                    # Get or create profile
                    try:
                        profile = obj.profile
                    except UserProfile.DoesNotExist:
                        profile = UserProfile.objects.create(
                            user=obj,
                            rola=rola,
                            aktywny=obj.is_active
                        )
                    
                    # Update role and sync active status
                    profile.rola = rola
                    profile.aktywny = obj.is_active
                    profile.save()
                    
                    # Success message
                    messages.success(
                        request,
                        f'✅ Rola użytkownika {obj.get_full_name() or obj.username} została zmieniona na: {rola.get_nazwa_display()}'
                    )
                except Role.DoesNotExist:
                    messages.error(request, 'Wybrana rola nie istnieje.')
                except Exception as e:
                    messages.error(request, f'Błąd podczas zapisywania roli: {str(e)}')

    def _update_profile_role(self, request, queryset, role_const, role_description_default):
        role_obj, created = Role.objects.get_or_create(
            nazwa=role_const,
            defaults={'opis': role_description_default}
        )
        updated_count = 0
        for user in queryset:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.rola = role_obj
            profile.aktywny = user.is_active  # Sync with User.is_active
            profile.save()
            updated_count += 1
        self.message_user(request, f'{updated_count} użytkowników otrzymało rolę {role_obj.get_nazwa_display()}.')

    @admin.action(description="Zmień rolę na Administrator")
    def make_admin_role(self, request, queryset):
        self._update_profile_role(request, queryset, Role.ADMIN, 'Pełne uprawnienia administracyjne')
    
    @admin.action(description="Zmień rolę na Edytor")
    def make_editor_role(self, request, queryset):
        self._update_profile_role(request, queryset, Role.EDITOR, 'Uprawnienia edytora')

    @admin.action(description="Zmień rolę na Czytelnik")
    def make_reader_role(self, request, queryset):
        self._update_profile_role(request, queryset, Role.READER, 'Podstawowe uprawnienia czytelnika')


# Re-register User model with our custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Role administration."""
    list_display = ['get_nazwa_display', 'opis', 'get_users_count']
    search_fields = ['nazwa', 'opis']
    readonly_fields = ('get_users_count',)
    
    fieldsets = (
        ('Informacje o roli', {'fields': ('nazwa', 'opis')}),
        ('Statystyki', {'fields': ('get_users_count',), 'classes': ('collapse',)})
    )
    
    @admin.display(description='Liczba użytkowników')
    def get_users_count(self, obj):
        """Count users with this role."""
        count = UserProfile.objects.filter(rola=obj, aktywny=True).count()
        total = UserProfile.objects.filter(rola=obj).count()
        return f"{count} aktywnych / {total} wszystkich"


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """User session administration."""
    list_display = [
        'get_user_display', 'login_time', 'get_session_duration', 
        'ip_address', 'is_active'
    ]
    list_filter = ['is_active', 'login_time']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'user__email', 'ip_address']
    readonly_fields = ['user', 'session_key', 'login_time', 'logout_time', 'user_agent', 'ip_address']
    date_hierarchy = 'login_time'
    ordering = ['-login_time']
    
    fieldsets = (
        ('Sesja', {'fields': ('user', 'is_active', 'session_key')}),
        ('Czas', {'fields': ('login_time', 'logout_time')}),
        ('Informacje techniczne', {'fields': ('ip_address', 'user_agent'), 'classes': ('collapse',)})
    )
    
    @admin.display(description='Użytkownik', ordering='user__username')
    def get_user_display(self, obj):
        return obj.user.get_full_name() or obj.user.email
    
    @admin.display(description='Czas trwania')
    def get_session_duration(self, obj):
        if obj.logout_time:
            duration = obj.logout_time - obj.login_time
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            if hours > 0:
                return f"{hours}g {minutes}m"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            return f"{seconds}s"
        elif obj.is_active:
            return format_html('<span style="color: green;">Aktywna</span>')
        return "Zakończona (brak danych)"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True


# Customize admin site appearance
admin.site.site_header = "Document Manager - Panel Administracyjny"
admin.site.site_title = "Document Manager Admin"
admin.site.index_title = "Zarządzanie systemem"