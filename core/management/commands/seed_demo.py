import os
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from accounts.models import User, Role
from accounts.signals import setup_system_roles_and_groups
from routes.models import Route
from core.models import SiteSettings, FieldConfig, ChoiceConfig, ALLOWED_FIELD_KEYS
from parcels.models import Parcel, ShipmentItem, ParcelStatusHistory, ParcelStatus, PaymentStatus, PaymentMethod
from parcels.services import create_parcel, transition_parcel_status, collect_parcel


class Command(BaseCommand):
    help = "Seeds initial configuration, routes, roles, and demo operational data for development."

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Explicit confirmation to run seeding in current environment'
        )

    def handle(self, *args, **options):
        # Environment and flag guard (Section 39)
        env_allowed = getattr(settings, 'ENABLE_DEMO_SEED', False) or os.environ.get('ENABLE_DEMO_SEED', 'False').lower() in ('true', '1')
        confirmed = options.get('confirm', False)

        if not (env_allowed or confirmed):
            raise CommandError(
                "Demo seeding is guarded and disabled in this environment. "
                "Set ENABLE_DEMO_SEED=True in .env or pass --confirm to proceed."
            )

        self.stdout.write(self.style.WARNING("Starting demo seeding for Northern Highways Transporters..."))

        # 1. Setup Roles & Groups
        setup_system_roles_and_groups()
        self.stdout.write(self.style.SUCCESS("✓ Synchronized system groups and permissions"))

        # 2. Site Settings
        site_settings = SiteSettings.load()
        site_settings.company_name = "Northern Highways Transporters"
        site_settings.currency = "KES"
        site_settings.head_office = "Nairobi"
        site_settings.support_phone = "+254 711 000000"
        site_settings.support_email = "info@northernhighways.co.ke"
        site_settings.allow_superuser_edit_after_dispatch = True
        site_settings.tracking_rate_limit_per_minute = 60
        site_settings.save()
        self.stdout.write(self.style.SUCCESS("✓ Site settings configured"))

        # 3. Dynamic Field Configurations
        default_fields = [
            ('sender_name', 'Sender Full Name', 'Enter sender full name', '', True, True, 1),
            ('sender_phone', 'Sender Phone Number', '+254 7...', 'Kenyan mobile phone number', True, True, 2),
            ('receiver_name', 'Receiver Full Name', 'Enter receiver full name', '', True, True, 3),
            ('receiver_phone', 'Receiver Phone Number', '+254 7...', 'Kenyan mobile phone number', True, True, 4),
            ('receiver_id_number', 'Receiver ID / Passport', 'National ID Number', 'Required for collection verification', True, True, 5),
            ('truck_plate_number', 'Bus / Truck Plate Number', 'e.g. KDC 123A', 'Assigned vehicle upon dispatch', False, True, 6),
            ('driver_name', 'Driver Full Name', 'Driver in charge', 'Designated vehicle driver', False, True, 7),
        ]
        for key, lbl, ph, ht, req, vis, ord_num in default_fields:
            FieldConfig.objects.get_or_create(
                field_key=key,
                defaults={
                    'label': lbl,
                    'placeholder': ph,
                    'help_text': ht,
                    'is_required': req,
                    'is_visible': vis,
                    'order': ord_num,
                    'is_active': True,
                }
            )
        self.stdout.write(self.style.SUCCESS("✓ Field configurations initialized"))

        # 4. Choice Configurations
        choices_data = [
            ('wrap_type', 'Box', 'Box / Carton', True, 1),
            ('wrap_type', 'Sack', 'Gunny Sack', False, 2),
            ('wrap_type', 'Envelope', 'Document Envelope', False, 3),
            ('wrap_type', 'Bundle', 'Bale / Bundle', False, 4),
            ('payment_method', 'CASH', 'Cash Counter Payment', True, 1),
            ('payment_method', 'MPESA', 'M-Pesa Mobile Money', False, 2),
            ('payment_status', 'PAID', 'Paid in Full', True, 1),
            ('payment_status', 'COD', 'Cash on Delivery (COD)', False, 2),
            ('payment_status', 'UNPAID', 'Unpaid Consignment', False, 3),
        ]
        for cat, k, lbl, is_def, ord_n in choices_data:
            ChoiceConfig.objects.get_or_create(
                category=cat,
                key=k,
                defaults={
                    'label': lbl,
                    'is_default': is_def,
                    'order': ord_n,
                    'is_active': True
                }
            )
        self.stdout.write(self.style.SUCCESS("✓ Choice configurations initialized"))

        # 5. Routes (Section 21)
        initial_routes = [
            ('Garissa', 'Garissa Main Terminal via Thika-Mwingi corridor'),
            ('Wajir', 'Wajir Town Terminal via Habaswein'),
            ('Kotulo Drop-off', 'Kotulo Waypoint drop-off station'),
            ('Elwak', 'Elwak Sub-county terminal'),
            ('Rhamu', 'Rhamu Town delivery point'),
            ('Lafey', 'Lafey Border Terminal'),
            ('Arabia', 'Arabia Town Drop-off'),
            ('Mandera', 'Mandera Central Office / Main Border Terminal'),
        ]
        created_routes = {}
        for r_name, desc in initial_routes:
            route_obj, _ = Route.objects.get_or_create(
                name=r_name,
                defaults={'origin': 'Nairobi', 'description': desc, 'is_active': True}
            )
            created_routes[r_name] = route_obj
        self.stdout.write(self.style.SUCCESS(f"✓ Initialized {len(created_routes)} routes"))

        # 6. Demo Users (Section 6 & 14)
        create_admin_allowed = getattr(settings, 'CREATE_DEMO_ADMIN', False) or os.environ.get('CREATE_DEMO_ADMIN', 'False').lower() in ('true', '1')
        self.stdout.write(self.style.WARNING("\n********************************************************"))
        self.stdout.write(self.style.WARNING("***        DEVELOPMENT / DEMO ONLY CREDENTIALS       ***"))
        self.stdout.write(self.style.WARNING("********************************************************\n"))

        demo_users_data = [
            ('admin', 'Super', 'Administrator', '0700111000', 'admin@northernhighways.co.ke', Role.SUPER_ADMIN, None, True),
            ('ops_manager', 'Mohamed', 'Farah', '0700222000', 'ops@northernhighways.co.ke', Role.OPERATIONS_MANAGER, None, False),
            ('counter_clerk', 'Fatuma', 'Ahmed', '0700333000', 'counter@northernhighways.co.ke', Role.COUNTER_STAFF, None, False),
            ('driver_ali', 'Ali', 'Hassan', '0700444000', 'ali@northernhighways.co.ke', Role.DISPATCH_STAFF, None, False),
            ('dest_garissa', 'Abdi', 'Kadir', '0700555000', 'garissa@northernhighways.co.ke', Role.DESTINATION_STAFF, created_routes['Garissa'], False),
            ('dest_mandera', 'Halima', 'Noor', '0700666000', 'mandera@northernhighways.co.ke', Role.DESTINATION_STAFF, created_routes['Mandera'], False),
            ('auditor_sam', 'Samuel', 'Kiptoo', '0700777000', 'audit@northernhighways.co.ke', Role.READ_ONLY, None, False),
        ]

        users = {}
        default_pwd = 'NHTPass2026!'
        for username, fname, lname, phone, email, role, assigned_r, is_super in demo_users_data:
            if is_super and not create_admin_allowed:
                self.stdout.write(self.style.WARNING(
                    "(!) Skipping demo superuser 'admin': CREATE_DEMO_ADMIN is False. "
                    "Set CREATE_DEMO_ADMIN=True to seed the demo superuser."
                ))
                continue

            user = User.objects.filter(username=username).first()
            if not user:
                user = User(
                    username=username,
                    first_name=fname,
                    last_name=lname,
                    phone=phone,
                    email=email,
                    role=role,
                    assigned_route=assigned_r,
                    is_staff=True,
                    is_superuser=is_super
                )
                user.set_password(default_pwd)
                user.save()
            users[username] = user
        self.stdout.write(self.style.SUCCESS(f"✓ Created/Verified {len(users)} operational demo users (Password: {default_pwd})"))

        # 7. Demo Parcels across lifecycle states
        if not Parcel.objects.exists():
            clerk = users['counter_clerk']

            # 1: RECEIVED_AT_HQ
            p1 = create_parcel(
                route=created_routes['Garissa'],
                sender_name="Ibrahim Noor",
                sender_phone="0712345678",
                receiver_name="Khadija Mohamed",
                receiver_phone="0723456789",
                receiver_id_number="28471920",
                payment_status=PaymentStatus.PAID,
                payment_method=PaymentMethod.MPESA,
                items_data=[
                    {'description': 'Spare Bus Engine Belts', 'wrap_type': 'Box', 'quantity': 2, 'unit_price': Decimal('750.00')},
                    {'description': 'Hydraulic Fluid Cans', 'wrap_type': 'Carton', 'quantity': 1, 'unit_price': Decimal('1200.00')}
                ],
                created_by=clerk
            )

            # 2: IN_TRANSIT
            p2 = create_parcel(
                route=created_routes['Mandera'],
                sender_name="Amina Warsame",
                sender_phone="0733123456",
                receiver_name="Sheikh Omar",
                receiver_phone="0744987654",
                receiver_id_number="19382049",
                payment_status=PaymentStatus.PAID,
                payment_method=PaymentMethod.CASH,
                items_data=[
                    {'description': 'Solar Inverter 5kVA', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('3500.00')}
                ],
                created_by=clerk
            )
            transition_parcel_status(
                parcel_id=p2.pk,
                new_status=ParcelStatus.IN_TRANSIT,
                user=users['ops_manager'],
                note="Loaded on Bus KDA 982T",
                truck_plate_number="KDA 982T",
                driver_name="Ali Hassan"
            )

            # 3: ARRIVED_AT_DESTINATION
            p3 = create_parcel(
                route=created_routes['Wajir'],
                sender_name="Hassan Adan",
                sender_phone="0755123456",
                receiver_name="Mariam Hussein",
                receiver_phone="0766123456",
                receiver_id_number="30291823",
                payment_status=PaymentStatus.COD,
                payment_method=PaymentMethod.CASH,
                items_data=[
                    {'description': 'Textiles & Somali Fabrics', 'wrap_type': 'Bundle', 'quantity': 3, 'unit_price': Decimal('800.00')}
                ],
                created_by=clerk
            )
            transition_parcel_status(
                parcel_id=p3.pk,
                new_status=ParcelStatus.IN_TRANSIT,
                user=users['ops_manager'],
                note="Dispatched",
                truck_plate_number="KBZ 441X",
                driver_name="Farah Osman"
            )
            transition_parcel_status(
                parcel_id=p3.pk,
                new_status=ParcelStatus.ARRIVED_AT_DESTINATION,
                user=users['ops_manager'],
                note="Offloaded at Wajir Town depot"
            )

            # 4: AWAITING_COLLECTION
            p4 = create_parcel(
                route=created_routes['Garissa'],
                sender_name="Yusuf Barre",
                sender_phone="0777123456",
                receiver_name="Ahmed Diriye",
                receiver_phone="0788123456",
                receiver_id_number="22910482",
                payment_status=PaymentStatus.PAID,
                payment_method=PaymentMethod.MPESA,
                items_data=[
                    {'description': 'Electronic Medical Thermometers', 'wrap_type': 'Box', 'quantity': 4, 'unit_price': Decimal('500.00')}
                ],
                created_by=clerk
            )
            transition_parcel_status(p4.pk, ParcelStatus.IN_TRANSIT, users['ops_manager'], "Dispatched", "KCG 112L", "Ali Hassan")
            transition_parcel_status(p4.pk, ParcelStatus.ARRIVED_AT_DESTINATION, users['dest_garissa'], "Arrived at Garissa")
            transition_parcel_status(p4.pk, ParcelStatus.AWAITING_COLLECTION, users['dest_garissa'], "Receiver notified via SMS")

            # 5: COLLECTED
            p5 = create_parcel(
                route=created_routes['Garissa'],
                sender_name="Khadra Duale",
                sender_phone="0799123456",
                receiver_name="Osman Gedi",
                receiver_phone="0711998877",
                receiver_id_number="18293041",
                payment_status=PaymentStatus.PAID,
                payment_method=PaymentMethod.CASH,
                items_data=[
                    {'description': 'Agricultural Pump Replacement Parts', 'wrap_type': 'Sack', 'quantity': 1, 'unit_price': Decimal('1500.00')}
                ],
                created_by=clerk
            )
            transition_parcel_status(p5.pk, ParcelStatus.IN_TRANSIT, users['ops_manager'], "Dispatched", "KDC 555M", "Ali Hassan")
            transition_parcel_status(p5.pk, ParcelStatus.ARRIVED_AT_DESTINATION, users['dest_garissa'], "Arrived at Garissa")
            transition_parcel_status(p5.pk, ParcelStatus.AWAITING_COLLECTION, users['dest_garissa'], "Ready for pickup")
            collect_parcel(p5.pk, collected_by_name="Osman Gedi", user=users['dest_garissa'], note="Verified National ID 18293041")

            self.stdout.write(self.style.SUCCESS("✓ Seeded sample consignments across all lifecycle stages"))

        self.stdout.write(self.style.SUCCESS("\n🎉 Demo seeding completed successfully!"))
        self.stdout.write("Super Admin: admin / NHTPass2026!")
        self.stdout.write("Ops Manager: ops_manager / NHTPass2026!")
        self.stdout.write("Counter Clerk: counter_clerk / NHTPass2026!")
        self.stdout.write("Destination Clerk (Garissa): dest_garissa / NHTPass2026!")
