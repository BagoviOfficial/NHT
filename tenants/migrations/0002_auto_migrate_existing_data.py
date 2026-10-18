from django.db import migrations


def migrate_existing_data_to_default_tenant(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    User = apps.get_model('accounts', 'User')
    Route = apps.get_model('routes', 'Route')
    Parcel = apps.get_model('parcels', 'Parcel')
    SiteSettings = apps.get_model('core', 'SiteSettings')
    FieldConfig = apps.get_model('core', 'FieldConfig')
    ChoiceConfig = apps.get_model('core', 'ChoiceConfig')
    AuditLog = apps.get_model('audit', 'AuditLog')

    # If any routes or parcels exist, link them to default tenant
    has_legacy_data = Route.objects.exists() or Parcel.objects.exists() or User.objects.exists()

    if has_legacy_data or not Tenant.objects.exists():
        default_tenant, _ = Tenant.objects.get_or_create(
            slug='nht',
            defaults={
                'name': 'Northern Highways Transporters',
                'subdomain': 'nht',
                'tracking_prefix': 'NHT',
                'head_office': 'Nairobi',
                'currency': 'KES',
                'support_phone': '+254 700 000000',
                'support_email': 'support@northernhighways.co.ke',
                'receipt_header': 'NORTHERN HIGHWAYS TRANSPORTERS\nParcel & Courier Express Services\nHead Office: Nairobi, Kenya',
                'receipt_footer': "Thank you for choosing Northern Highways Transporters.\nGoods received in good order.\nLuggage stored at owner's risk after 48 hours.",
                'is_active': True,
            }
        )

        Route.objects.filter(tenant=None).update(tenant=default_tenant)
        Parcel.objects.filter(tenant=None).update(tenant=default_tenant)
        AuditLog.objects.filter(tenant=None).update(tenant=default_tenant)
        FieldConfig.objects.filter(tenant=None).update(tenant=default_tenant)
        ChoiceConfig.objects.filter(tenant=None).update(tenant=default_tenant)
        SiteSettings.objects.filter(tenant=None).update(tenant=default_tenant)

        # Update non-superuser staff accounts to belong to default tenant
        User.objects.filter(is_superuser=False, tenant=None).update(tenant=default_tenant)


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        ('accounts', '0002_user_tenant'),
        ('routes', '0002_route_tenant_alter_route_name_alter_route_slug_and_more'),
        ('parcels', '0002_parcel_tenant_alter_parcel_tracking_number'),
        ('core', '0002_alter_choiceconfig_unique_together_and_more'),
        ('audit', '0002_auditlog_tenant'),
    ]

    operations = [
        migrations.RunPython(migrate_existing_data_to_default_tenant, reverse_func),
    ]
