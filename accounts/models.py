from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', _('Super Admin')
    OPERATIONS_MANAGER = 'OPERATIONS_MANAGER', _('Operations Manager')
    COUNTER_STAFF = 'COUNTER_STAFF', _('Counter / Front Desk Staff')
    DISPATCH_STAFF = 'DISPATCH_STAFF', _('Dispatch / Transport Staff')
    DESTINATION_STAFF = 'DESTINATION_STAFF', _('Destination / Collection Staff')
    READ_ONLY = 'READ_ONLY', _('Reporting / Read Only')


class User(AbstractUser):
    """
    Custom user model for Northern Highways Transporters Parcel Management System.
    Includes unique phone number and explicit role-based access control.
    """
    phone = models.CharField(
        max_length=30,
        unique=True,
        help_text=_("Staff phone number (must be unique).")
    )
    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.COUNTER_STAFF,
        db_index=True,
        help_text=_("System role defining operational permissions.")
    )
    assigned_route = models.ForeignKey(
        'routes.Route',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_staff',
        help_text=_("Assigned destination/branch route (required for destination collection staff).")
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='users',
        help_text=_("Associated client organization (null for Platform Super Admins).")
    )

    class Meta:
        ordering = ['username']
        verbose_name = _('User')
        verbose_name_plural = _('Users')

    def __str__(self):
        full_name = self.get_full_name()
        display = full_name if full_name else self.username
        return f"{display} ({self.get_role_display()})"

    @property
    def is_super_admin(self):
        return self.role == Role.SUPER_ADMIN or self.is_superuser

    @property
    def is_operations_manager(self):
        return self.role == Role.OPERATIONS_MANAGER

    @property
    def is_counter_staff(self):
        return self.role == Role.COUNTER_STAFF

    @property
    def is_dispatch_staff(self):
        return self.role == Role.DISPATCH_STAFF

    @property
    def is_destination_staff(self):
        return self.role == Role.DESTINATION_STAFF

    @property
    def is_read_only(self):
        return self.role == Role.READ_ONLY

    # Permission helper properties
    @property
    def can_manage_users(self):
        return self.is_super_admin

    @property
    def can_manage_routes(self):
        return self.is_super_admin

    @property
    def can_manage_config(self):
        return self.is_super_admin

    @property
    def can_create_parcel(self):
        return self.is_super_admin or self.is_operations_manager or self.is_counter_staff

    @property
    def can_edit_parcel(self):
        return self.is_super_admin or self.is_operations_manager or self.is_counter_staff

    @property
    def can_cancel_parcel(self):
        return self.is_super_admin or self.is_operations_manager

    @property
    def can_dispatch_parcel(self):
        return self.is_super_admin or self.is_operations_manager or self.is_dispatch_staff

    @property
    def can_mark_arrival(self):
        return self.is_super_admin or self.is_operations_manager or self.is_destination_staff

    @property
    def can_mark_awaiting(self):
        return self.is_super_admin or self.is_operations_manager or self.is_destination_staff

    @property
    def can_manage_collection(self):
        return (
            self.is_super_admin
            or self.is_operations_manager
            or self.is_counter_staff
            or self.is_destination_staff
        )

    @property
    def can_view_reports(self):
        return (
            self.is_super_admin
            or self.is_operations_manager
            or self.is_read_only
        )

    @property
    def can_view_audit_logs(self):
        return self.is_super_admin

    @property
    def can_view_financials(self):
        """Dispatch and destination staff should not see full company financial statements."""
        return self.is_super_admin or self.is_operations_manager or self.is_counter_staff or self.is_read_only
