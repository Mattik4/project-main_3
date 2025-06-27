from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.apps import apps


@receiver(post_migrate)
def create_default_roles(sender, **kwargs):
    """
    Create default roles after migration.
    This runs after every migrate command.
    """
    # Only run for users app
    if sender.name != 'users':
        return
        
    # Get the Role model
    try:
        Role = apps.get_model('users', 'Role')
    except LookupError:
        # Model doesn't exist yet
        return
    
    # Define default roles
    default_roles = [
        {
            'nazwa': 'administrator',
            'opis': 'Pełne uprawnienia administracyjne - zarządzanie użytkownikami, dokumentami i systemem'
        },
        {
            'nazwa': 'edytor', 
            'opis': 'Uprawnienia edytora - tworzenie, edytowanie i zarządzanie dokumentami'
        },
        {
            'nazwa': 'czytelnik',
            'opis': 'Uprawnienia czytelnika - tylko odczyt dokumentów'
        }
    ]
    
    # Create roles if they don't exist
    created_count = 0
    for role_data in default_roles:
        role, created = Role.objects.get_or_create(
            nazwa=role_data['nazwa'],
            defaults={'opis': role_data['opis']}
        )
        if created:
            created_count += 1
            print(f"✓ Created role: {role.nazwa}")
    
    if created_count > 0:
        print(f"✅ Created {created_count} default roles successfully!")
    else:
        print("All default roles already exist.")
