from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError


class Role(models.Model):
    """Role model for user permissions"""
    ADMIN = 'administrator'
    EDITOR = 'edytor'
    READER = 'czytelnik'
    
    ROLE_CHOICES = [
        (ADMIN, 'Administrator'),
        (EDITOR, 'Edytor'),
        (READER, 'Czytelnik'),
    ]
    
    nazwa = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    opis = models.TextField(blank=True)
    
    def __str__(self):
        return self.get_nazwa_display()
    
    class Meta:
        db_table = 'rola'
        verbose_name = 'Rola'
        verbose_name_plural = 'Role'


class UserProfile(models.Model):
    """Extended user profile with additional fields"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    rola = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True)
    aktywny = models.BooleanField(default=True)
    telefon = models.CharField(max_length=20, blank=True)
    stanowisko = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    data_urodzenia = models.DateField(blank=True, null=True)
    
    # Two-factor authentication fields (for future implementation)
    dwuetapowa_weryfikacja = models.BooleanField(default=False)
    
    # Privacy settings
    profil_publiczny = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.user.email}) - {self.rola if self.rola else 'Brak roli'}"
    
    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}".strip()
    
    @property
    def is_admin(self):
        return self.rola and self.rola.nazwa == Role.ADMIN
    
    @property
    def is_editor(self):
        return self.rola and self.rola.nazwa == Role.EDITOR
    
    @property
    def is_reader(self):
        return self.rola and self.rola.nazwa == Role.READER
    
    def clean(self):
        """Validate that user has first_name and last_name"""
        if not self.user.first_name:
            raise ValidationError('Imię jest wymagane.')
        if not self.user.last_name:
            raise ValidationError('Nazwisko jest wymagane.')
        if not self.user.email:
            raise ValidationError('Email jest wymagany.')
    
    class Meta:
        db_table = 'user_profile'
        verbose_name = 'Profil użytkownika'
        verbose_name_plural = 'Profile użytkowników'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create user profile when user is created"""
    if created:
        # Get or create default role (Czytelnik)
        try:
            default_role = Role.objects.get(nazwa=Role.READER)
        except Role.DoesNotExist:
            # Create default role if it doesn't exist
            default_role = Role.objects.create(
                nazwa=Role.READER,
                opis='Podstawowa rola z prawami do odczytu'
            )
        
        # Create profile with default role
        UserProfile.objects.create(
            user=instance, 
            rola=default_role,
            aktywny=True
        )
        
        print(f"✅ Utworzono profil dla użytkownika: {instance.get_full_name()} z rolą: {default_role.get_nazwa_display()}")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save user profile when user is saved"""
    # Only save if profile exists (to avoid recursion on creation)
    if hasattr(instance, 'profile') and not kwargs.get('created', False):
        instance.profile.save()


class UserSession(models.Model):
    """Track user sessions for security"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions_log')
    session_key = models.CharField(max_length=40)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.login_time}"
    
    class Meta:
        db_table = 'user_session'
        verbose_name = 'Sesja użytkownika'
        verbose_name_plural = 'Sesje użytkowników'
        ordering = ['-login_time']
