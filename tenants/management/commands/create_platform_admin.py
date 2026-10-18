from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Creates or elevates a user to Global SaaS Platform Owner (superuser without tenant association)."

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help="Administrator username")
        parser.add_argument('--password', type=str, required=True, help="Administrator password")
        parser.add_argument('--phone', type=str, required=True, help="Unique phone number")
        parser.add_argument('--email', type=str, default='', help="Optional contact email")

    def handle(self, *args, **options):
        username = options['username'].strip()
        password = options['password'].strip()
        phone = options['phone'].strip()
        email = options.get('email', '').strip()

        user = User.objects.filter(username=username).first()
        if user:
            user.set_password(password)
            user.phone = phone
            if email:
                user.email = email
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.tenant = None
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Existing user '{username}' elevated to SaaS Platform Super Admin."))
        else:
            if User.objects.filter(phone=phone).exists():
                raise CommandError(f"Phone number '{phone}' is already in use by another user.")

            user = User.objects.create_superuser(
                username=username,
                password=password,
                phone=phone,
                email=email,
                tenant=None
            )
            self.stdout.write(self.style.SUCCESS(f"Global SaaS Platform Super Admin '{username}' created successfully."))
