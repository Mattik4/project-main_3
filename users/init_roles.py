from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import Role, UserProfile


class Command(BaseCommand):
    help = 'Initialize default roles and optionally create admin user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-admin',
            action='store_true',
            help='Create admin user if not exists',
        )

    def handle(self, *args, **options):
        self.stdout.write('Initializing roles...')
        
        # Create default roles
        roles_data = [
            {
                'nazwa': Role.ADMIN,
                'opis': 'Pełne uprawnienia administracyjne - zarządzanie użytkownikami, dokumentami i systemem'
            },
            {
                'nazwa': Role.EDITOR,
                'opis': 'Uprawnienia edytora - tworzenie, edytowanie i zarządzanie dokumentami'
            },
            {
                'nazwa': Role.READER,
                'opis': 'Uprawnienia czytelnika - tylko odczyt dokumentów'
            }
        ]
        
        created_roles = 0
        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                nazwa=role_data['nazwa'],
                defaults={'opis': role_data['opis']}
            )
            if created:
                created_roles += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created role: {role.get_nazwa_display()}')
                )
            else:
                self.stdout.write(f'- Role already exists: {role.get_nazwa_display()}')
        
        self.stdout.write(f'\nCreated {created_roles} new roles.')
        
        # Create admin user if requested
        if options['create_admin']:
            self.create_admin_user()
        
        self.stdout.write(
            self.style.SUCCESS('\n✓ Initialization completed successfully!')
        )
        self.stdout.write('\nNastępne kroki:')
        self.stdout.write('1. Uruchom serwer: python manage.py runserver')
        self.stdout.write('2. Idź do /admin/ aby dodać użytkowników')
        self.stdout.write('3. Loguj się na głównej stronie używając email + hasło')

    def create_admin_user(self):
        self.stdout.write('\nCreating admin user...')
        
        # Check if admin user already exists
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write('- Admin user already exists')
            return
        
        email = input('Enter admin email: ')
        
        if not email:
            self.stdout.write(self.style.ERROR('Email is required'))
            return
        
        # Check if email is taken
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.ERROR(f'Email "{email}" is already taken'))
            return
        
        first_name = input('Enter first name: ')
        last_name = input('Enter last name: ')
        
        if not first_name or not last_name:
            self.stdout.write(self.style.ERROR('First name and last name are required'))
            return
        
        # Generate username from email
        username = email.split('@')[0]
        if User.objects.filter(username=username).exists():
            username = f"{username}_admin"
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_staff=True,
            is_superuser=True
        )
        
        # Set password
        password = input('Enter password (leave empty for "admin123"): ') or 'admin123'
        user.set_password(password)
        user.save()
        
        # Create or update profile with admin role
        admin_role = Role.objects.get(nazwa=Role.ADMIN)
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.rola = admin_role
        profile.aktywny = True
        profile.save()
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ Admin user created successfully!')
        )
        self.stdout.write(f'  Name: {first_name} {last_name}')
        self.stdout.write(f'  Email: {email}')
        self.stdout.write(f'  Password: {password}')
        self.stdout.write('  Please change the password after first login!')
        self.stdout.write(f'  Login at: http://127.0.0.1:8000/users/login/')