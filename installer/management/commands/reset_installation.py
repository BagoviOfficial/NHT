from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from installer.utils import get_lock_file
from installer.middleware import InstallationRedirectMiddleware


class Command(BaseCommand):
    help = "Resets the installer lock file to allow re-running the WordPress-style setup wizard."

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help="Confirmation flag required to prevent accidental lock resets"
        )
        parser.add_argument(
            '--flush-db',
            action='store_true',
            help="Also flush the database completely to start from a blank state"
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            raise CommandError("You must provide the --confirm flag to reset the installation.")

        lock = get_lock_file()
        if lock.exists():
            try:
                lock.unlink()
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted lock file: {lock}"))
            except Exception as e:
                raise CommandError(f"Failed to remove lock file: {e}")
        else:
            self.stdout.write(self.style.WARNING("Lock file (.installed) did not exist."))

        InstallationRedirectMiddleware.reset_installed_cache()

        if options['flush_db']:
            self.stdout.write(self.style.NOTICE("Flushing database tables..."))
            call_command('flush', interactive=False)
            self.stdout.write(self.style.SUCCESS("Database flushed."))

        self.stdout.write(self.style.SUCCESS(
            "\nInstallation lock reset complete.\n"
            "You can now access http://localhost:8000/ or /install/ to run the setup wizard.\n"
        ))
