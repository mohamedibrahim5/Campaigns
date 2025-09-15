from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from hub.models import Candidate
import secrets
import string

User = get_user_model()

class Command(BaseCommand):
    help = 'Create user accounts for all candidates with login credentials'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password-length',
            type=int,
            default=12,
            help='Length of generated passwords (default: 12)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing users with new passwords'
        )

    def handle(self, *args, **options):
        password_length = options['password_length']
        force = options['force']
        
        self.stdout.write(
            self.style.SUCCESS('Creating user accounts for candidates...')
        )
        
        created_count = 0
        updated_count = 0
        
        for candidate in Candidate.objects.filter(is_active=True):
            # Generate username from candidate name
            username = candidate.name.lower().replace(' ', '_').replace('-', '_')
            # Remove special characters
            username = ''.join(c for c in username if c.isalnum() or c == '_')
            
            # Generate secure password
            password = self.generate_password(password_length)
            
            # Check if user already exists
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': candidate.email or f'{username}@election360.local',
                    'first_name': candidate.name.split()[0] if candidate.name.split() else '',
                    'last_name': ' '.join(candidate.name.split()[1:]) if len(candidate.name.split()) > 1 else '',
                    'is_staff': True,  # Give staff access
                }
            )
            
            if created:
                user.set_password(password)
                user.save()
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created user for {candidate.name}: {username} / {password}'
                    )
                )
            elif force:
                user.set_password(password)
                user.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'↻ Updated password for {candidate.name}: {username} / {password}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠ User already exists for {candidate.name}: {username} (use --force to update)'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary: {created_count} users created, {updated_count} users updated'
            )
        )
        
        # Display all candidate landing page URLs and dashboard access
        self.stdout.write(
            self.style.SUCCESS('\n=== CANDIDATE LANDING PAGE URLs ===')
        )
        for candidate in Candidate.objects.filter(is_active=True):
            landing_url = f'https://3ad99fb5c246.ngrok-free.app/hub/candidate/{candidate.id}/'
            dashboard_url = f'https://3ad99fb5c246.ngrok-free.app/hub/candidate/{candidate.id}/dashboard/'
            username = candidate.name.lower().replace(' ', '_').replace('-', '_')
            username = ''.join(c for c in username if c.isalnum() or c == '_')
            
            self.stdout.write(f'\n{candidate.name}:')
            self.stdout.write(f'  Landing Page: {landing_url}')
            self.stdout.write(f'  Dashboard: {dashboard_url}')
            self.stdout.write(f'  Username: {username}')
            self.stdout.write(f'  Password: [Generated above]')
    
    def generate_password(self, length=12):
        """Generate a secure random password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        return password
