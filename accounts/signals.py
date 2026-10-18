from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from .models import User, Role


def setup_system_roles_and_groups():
    """
    Creates standard Groups for each role and assigns baseline Django permissions.
    """
    groups_config = {
        Role.SUPER_ADMIN: {
            'is_staff': True,
        },
        Role.OPERATIONS_MANAGER: {
            'is_staff': True,
            'permissions': [
                'view_parcel', 'add_parcel', 'change_parcel',
                'view_shipmentitem', 'add_shipmentitem', 'change_shipmentitem',
                'view_parcelstatushistory', 'view_route',
            ]
        },
        Role.COUNTER_STAFF: {
            'is_staff': True,
            'permissions': [
                'view_parcel', 'add_parcel', 'change_parcel',
                'view_shipmentitem', 'add_shipmentitem', 'change_shipmentitem',
                'view_parcelstatushistory', 'view_route',
            ]
        },
        Role.DISPATCH_STAFF: {
            'is_staff': True,
            'permissions': [
                'view_parcel', 'change_parcel',
                'view_shipmentitem', 'view_parcelstatushistory', 'view_route',
            ]
        },
        Role.DESTINATION_STAFF: {
            'is_staff': True,
            'permissions': [
                'view_parcel', 'change_parcel',
                'view_shipmentitem', 'view_parcelstatushistory', 'view_route',
            ]
        },
        Role.READ_ONLY: {
            'is_staff': True,
            'permissions': [
                'view_parcel', 'view_shipmentitem', 'view_parcelstatushistory', 'view_route',
            ]
        },
    }

    for role_name, config in groups_config.items():
        group, _ = Group.objects.get_or_create(name=role_name)
        perms = config.get('permissions', [])
        for codename in perms:
            perm = Permission.objects.filter(codename=codename).first()
            if perm:
                group.permissions.add(perm)


@receiver(post_save, sender=User)
def sync_user_role_and_group(sender, instance, created, **kwargs):
    """
    Ensure the user is member of the corresponding Group based on their role
    and set is_staff=True appropriately.
    """
    # Auto-adjust is_staff
    should_be_staff = True
    
    updates = {}
    if instance.is_staff != should_be_staff:
        updates['is_staff'] = should_be_staff
    if instance.tenant is None and instance.role == Role.SUPER_ADMIN and not instance.is_superuser:
        updates['is_superuser'] = True
    elif instance.tenant is not None and instance.is_superuser:
        updates['is_superuser'] = False

    if updates:
        User.objects.filter(pk=instance.pk).update(**updates)

    # Assign group
    group, _ = Group.objects.get_or_create(name=instance.role)
    if not instance.groups.filter(name=instance.role).exists():
        # Clear other role groups
        for role_choice in Role.values:
            if role_choice != instance.role:
                old_group = Group.objects.filter(name=role_choice).first()
                if old_group:
                    instance.groups.remove(old_group)
        instance.groups.add(group)
