import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from parcels.models import (
    Branch, UserProfile, ShippingRate, Parcel,
    ParcelTrackingLog, TransitManifest, PickupRequest, CustomerInquiry
)


class Command(BaseCommand):
    help = 'Seeds database with realistic demo branches, users, rates, parcels, manifests, and inquiries.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting database seed...'))

        # 1. Shipping Rates
        rates_data = [
            {
                'service_type': 'STANDARD',
                'base_price': 5.00,
                'per_kg_rate': 2.50,
                'fragile_fee': 4.00,
                'insurance_rate_pct': 1.50,
                'tax_pct': 5.00,
                'delivery_time_frame': '3 - 5 Business Days'
            },
            {
                'service_type': 'EXPRESS',
                'base_price': 12.00,
                'per_kg_rate': 4.50,
                'fragile_fee': 6.00,
                'insurance_rate_pct': 1.50,
                'tax_pct': 5.00,
                'delivery_time_frame': '1 - 2 Business Days'
            },
            {
                'service_type': 'SAME_DAY',
                'base_price': 25.00,
                'per_kg_rate': 6.00,
                'fragile_fee': 8.00,
                'insurance_rate_pct': 2.00,
                'tax_pct': 5.00,
                'delivery_time_frame': 'Guaranteed Same-Day Delivery'
            },
        ]
        for r_info in rates_data:
            ShippingRate.objects.update_or_create(
                service_type=r_info['service_type'],
                defaults=r_info
            )
        self.stdout.write(self.style.SUCCESS('Shipping rates seeded.'))

        # 2. Branches
        branches_data = [
            {
                'code': 'NYC-01',
                'name': 'New York Midtown Central Hub',
                'branch_type': 'MAIN_HUB',
                'phone': '+1 (212) 555-0101',
                'email': 'nyc-hub@swiftparcel.com',
                'address': '450 7th Ave, Manhattan',
                'city': 'New York',
                'state': 'NY',
                'postal_code': '10123',
                'country': 'United States',
                'is_active': True,
            },
            {
                'code': 'LAX-01',
                'name': 'Los Angeles Pacific Gateway Hub',
                'branch_type': 'MAIN_HUB',
                'phone': '+1 (310) 555-0182',
                'email': 'lax-hub@swiftparcel.com',
                'address': '5757 W Century Blvd',
                'city': 'Los Angeles',
                'state': 'CA',
                'postal_code': '90045',
                'country': 'United States',
                'is_active': True,
            },
            {
                'code': 'ORD-01',
                'name': 'Chicago Central Sorting Facility',
                'branch_type': 'DISTRIBUTION',
                'phone': '+1 (312) 555-0144',
                'email': 'ord-sort@swiftparcel.com',
                'address': '10000 W O\'Hare Ave',
                'city': 'Chicago',
                'state': 'IL',
                'postal_code': '60666',
                'country': 'United States',
                'is_active': True,
            },
            {
                'code': 'MIA-01',
                'name': 'Miami Coastal Logistics Station',
                'branch_type': 'LOCAL_OFFICE',
                'phone': '+1 (305) 555-0199',
                'email': 'mia-office@swiftparcel.com',
                'address': '2100 NW 42nd Ave',
                'city': 'Miami',
                'state': 'FL',
                'postal_code': '33142',
                'country': 'United States',
                'is_active': True,
            },
            {
                'code': 'SEA-01',
                'name': 'Seattle Pacific Northwest Office',
                'branch_type': 'LOCAL_OFFICE',
                'phone': '+1 (206) 555-0133',
                'email': 'sea-office@swiftparcel.com',
                'address': '17801 International Blvd',
                'city': 'Seattle',
                'state': 'WA',
                'postal_code': '98158',
                'country': 'United States',
                'is_active': True,
            }
        ]

        created_branches = {}
        for b_data in branches_data:
            branch_obj, _ = Branch.objects.update_or_create(
                code=b_data['code'],
                defaults=b_data
            )
            created_branches[b_data['code']] = branch_obj
        self.stdout.write(self.style.SUCCESS(f'{len(created_branches)} Branches seeded.'))

        # 3. Users & Roles
        def create_user_with_profile(username, email, password, first_name, last_name, role, branch=None, is_superuser=False, vehicle='', plate=''):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_staff': is_superuser or (role in ['ADMIN', 'BRANCH_STAFF']),
                    'is_superuser': is_superuser,
                }
            )
            user.set_password(password)
            user.save()

            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'role': role,
                    'branch': branch,
                    'phone': '+1 (555) 012-3456',
                    'city': branch.city if branch else 'New York',
                    'vehicle_type': vehicle,
                    'license_plate': plate,
                    'is_available': True,
                }
            )
            return user

        # Admin
        admin_user = create_user_with_profile(
            'admin', 'admin@swiftparcel.com', 'admin123',
            'Alexander', 'Vance', 'ADMIN',
            branch=created_branches['NYC-01'], is_superuser=True
        )

        # Branch Staff
        staff_nyc = create_user_with_profile(
            'staff_nyc', 'staff.nyc@swiftparcel.com', 'staff123',
            'Emily', 'Watson', 'BRANCH_STAFF',
            branch=created_branches['NYC-01']
        )
        staff_lax = create_user_with_profile(
            'staff_lax', 'staff.lax@swiftparcel.com', 'staff123',
            'Marcus', 'Chen', 'BRANCH_STAFF',
            branch=created_branches['LAX-01']
        )

        # Couriers
        rider_alex = create_user_with_profile(
            'rider_alex', 'alex.rider@swiftparcel.com', 'rider123',
            'Alex', 'Rivera', 'COURIER',
            branch=created_branches['NYC-01'],
            vehicle='Honda PCX 160 Scooter', plate='NY-DLV-882'
        )
        rider_sam = create_user_with_profile(
            'rider_sam', 'sam.rider@swiftparcel.com', 'rider123',
            'Samantha', 'Miller', 'COURIER',
            branch=created_branches['LAX-01'],
            vehicle='Ford Transit Custom Van', plate='CA-EXP-401'
        )

        # Customer
        customer_user = create_user_with_profile(
            'customer1', 'customer@example.com', 'customer123',
            'James', 'Sterling', 'CUSTOMER',
            branch=None
        )
        self.stdout.write(self.style.SUCCESS('Users and profiles seeded.'))

        # 4. Realistic Parcels with Tracking Logs
        parcels_mock = [
            {
                'tracking_number': 'PRCL-202610-829104',
                'security_otp': '782914',
                'sender_name': 'James Sterling',
                'sender_phone': '+1 (212) 555-0199',
                'sender_email': 'customer@example.com',
                'sender_address': '742 Evergreen Terrace, Apt 4B',
                'sender_city': 'New York',
                'sender_user': customer_user,
                'receiver_name': 'Dr. Robert Langdon',
                'receiver_phone': '+1 (310) 555-8832',
                'receiver_email': 'rlangdon@harvard.edu',
                'receiver_address': '10880 Wilshire Blvd, Suite 1400',
                'receiver_city': 'Los Angeles',
                'origin_branch': created_branches['NYC-01'],
                'destination_branch': created_branches['LAX-01'],
                'current_branch': created_branches['ORD-01'],
                'delivery_type': 'DOORSTEP',
                'service_type': 'EXPRESS',
                'category': 'ELECTRONICS',
                'item_description': 'Dell XPS 15 Developer Laptop & Thunderbolt 4 Dock in foam casing',
                'weight_kg': 3.80,
                'length_cm': 38.0,
                'width_cm': 28.0,
                'height_cm': 12.0,
                'is_fragile': True,
                'declared_value': 1850.00,
                'status': 'IN_TRANSIT',
                'payment_status': 'PAID',
                'payment_method': 'CARD',
                'assigned_courier': None,
                'created_by': staff_nyc,
                'logs': [
                    ('BOOKED', created_branches['NYC-01'], 'New York Midtown Hub', 'Consignment registered and booking accepted at counter.', -48),
                    ('RECEIVED_AT_ORIGIN', created_branches['NYC-01'], 'New York Midtown Hub', 'Security screened, weighed and dimension verified.', -40),
                    ('IN_SORTING', created_branches['NYC-01'], 'New York Hub - Sorting Bay A', 'Sorted and packed into West Coast container bag #NYC-LAX-401.', -32),
                    ('IN_TRANSIT', created_branches['ORD-01'], 'Chicago Central Sorting Hub', 'Arrived at Chicago transit cross-dock; awaiting flight connection to LAX.', -8),
                ]
            },
            {
                'tracking_number': 'PRCL-202610-449120',
                'security_otp': '419082',
                'sender_name': 'Apex Legal Partners LLP',
                'sender_phone': '+1 (310) 555-3310',
                'sender_email': 'docs@apexlegal.com',
                'sender_address': '400 S Hope St, 20th Floor',
                'sender_city': 'Los Angeles',
                'sender_user': None,
                'receiver_name': 'Rachel Green',
                'receiver_phone': '+1 (212) 555-7741',
                'receiver_email': 'rachel.green@ralphlauren.com',
                'receiver_address': '650 Madison Ave',
                'receiver_city': 'New York',
                'origin_branch': created_branches['LAX-01'],
                'destination_branch': created_branches['NYC-01'],
                'current_branch': created_branches['NYC-01'],
                'delivery_type': 'DOORSTEP',
                'service_type': 'EXPRESS',
                'category': 'DOCUMENT',
                'item_description': 'Original notarized partnership deeds and signed contracts',
                'weight_kg': 0.60,
                'length_cm': 32.0,
                'width_cm': 24.0,
                'height_cm': 3.0,
                'is_fragile': False,
                'declared_value': 200.00,
                'status': 'OUT_FOR_DELIVERY',
                'payment_status': 'PAID',
                'payment_method': 'BANK_TRANSFER',
                'assigned_courier': rider_alex,
                'created_by': staff_lax,
                'logs': [
                    ('BOOKED', created_branches['LAX-01'], 'LAX Pacific Hub', 'Package registered by sender.', -36),
                    ('RECEIVED_AT_ORIGIN', created_branches['LAX-01'], 'LAX Pacific Hub', 'Item checked in and dispatched onto red-eye flight.', -28),
                    ('RECEIVED_AT_DESTINATION', created_branches['NYC-01'], 'NYC Midtown Hub', 'Bag arrived and sorted to local delivery depot.', -6),
                    ('OUT_FOR_DELIVERY', created_branches['NYC-01'], 'NYC Delivery Route 4', 'Dispatched with Courier Alex Rivera on route for delivery.', -2),
                ]
            },
            {
                'tracking_number': 'PRCL-202610-110294',
                'security_otp': '994821',
                'sender_name': 'Midwest Artisan Ceramics',
                'sender_phone': '+1 (312) 555-6677',
                'sender_email': 'info@midwestceramics.com',
                'sender_address': '224 N Michigan Ave',
                'sender_city': 'Chicago',
                'sender_user': None,
                'receiver_name': 'Carlos Santana',
                'receiver_phone': '+1 (305) 555-9012',
                'receiver_email': 'carlos@santanaart.com',
                'receiver_address': 'Hold at Miami Coastal Logistics Station',
                'receiver_city': 'Miami',
                'origin_branch': created_branches['ORD-01'],
                'destination_branch': created_branches['MIA-01'],
                'current_branch': created_branches['MIA-01'],
                'delivery_type': 'BRANCH_PICKUP',
                'service_type': 'STANDARD',
                'category': 'FRAGILE',
                'item_description': 'Handmade Japanese Raku Glazed Ceramic Tea Urn (Fragile)',
                'weight_kg': 4.20,
                'length_cm': 35.0,
                'width_cm': 35.0,
                'height_cm': 40.0,
                'is_fragile': True,
                'declared_value': 750.00,
                'status': 'READY_FOR_PICKUP',
                'payment_status': 'PAID',
                'payment_method': 'CARD',
                'assigned_courier': None,
                'created_by': admin_user,
                'logs': [
                    ('BOOKED', created_branches['ORD-01'], 'Chicago Hub', 'Booking registered with fragile handling requested.', -72),
                    ('IN_TRANSIT', created_branches['ORD-01'], 'Interstate Freight I-65', 'Consignment loaded on refrigerated fragile transport trailer.', -48),
                    ('RECEIVED_AT_DESTINATION', created_branches['MIA-01'], 'Miami Coastal Station', 'Consignment unloaded into secure storage hold.', -12),
                    ('READY_FOR_PICKUP', created_branches['MIA-01'], 'Miami Station Counter Shelf B3', 'Customer notified by SMS/Email. Ready for customer pickup with OTP.', -4),
                ]
            },
            {
                'tracking_number': 'PRCL-202610-771239',
                'security_otp': '610482',
                'sender_name': 'BioTech Labs Seattle',
                'sender_phone': '+1 (206) 555-4433',
                'sender_email': 'dispatch@biotechseattle.io',
                'sender_address': '401 Terry Ave N',
                'sender_city': 'Seattle',
                'sender_user': None,
                'receiver_name': 'Sarah Connor',
                'receiver_phone': '+1 (212) 555-9988',
                'receiver_email': 'sconnor@cyberdyne.org',
                'receiver_address': '350 5th Ave, Floor 44',
                'receiver_city': 'New York',
                'origin_branch': created_branches['SEA-01'],
                'destination_branch': created_branches['NYC-01'],
                'current_branch': created_branches['NYC-01'],
                'delivery_type': 'DOORSTEP',
                'service_type': 'SAME_DAY',
                'category': 'ELECTRONICS',
                'item_description': 'Calibrated Thermal Monitoring Sensors and Diagnostic Probes',
                'weight_kg': 2.10,
                'length_cm': 25.0,
                'width_cm': 20.0,
                'height_cm': 15.0,
                'is_fragile': True,
                'declared_value': 3200.00,
                'status': 'DELIVERED',
                'payment_status': 'PAID',
                'payment_method': 'CARD',
                'assigned_courier': rider_alex,
                'created_by': admin_user,
                'logs': [
                    ('BOOKED', created_branches['SEA-01'], 'Seattle Office', 'Priority Same-Day parcel booked.', -24),
                    ('IN_TRANSIT', created_branches['SEA-01'], 'Direct Express Flight DL-892', 'Loaded on direct morning priority freight flight.', -18),
                    ('RECEIVED_AT_DESTINATION', created_branches['NYC-01'], 'NYC Midtown Hub', 'Unloaded at NYC airport ramp and dispatched directly.', -8),
                    ('OUT_FOR_DELIVERY', created_branches['NYC-01'], 'Courier Van NY-DLV-882', 'Out for direct delivery to Empire State Building.', -4),
                    ('DELIVERED', created_branches['NYC-01'], '350 5th Ave, Floor 44', 'Delivered to recipient Sarah Connor. OTP verification confirmed.', -1),
                ]
            },
            {
                'tracking_number': 'PRCL-202610-338192',
                'security_otp': '182054',
                'sender_name': 'Fifth Ave Fashion Outlet',
                'sender_phone': '+1 (212) 555-6611',
                'sender_email': 'sales@fifthfashion.com',
                'sender_address': '720 5th Ave',
                'sender_city': 'New York',
                'sender_user': customer_user,
                'receiver_name': 'Michael Jordan',
                'receiver_phone': '+1 (312) 555-2323',
                'receiver_email': 'mj23@jumpman.com',
                'receiver_address': '2700 Point Dr',
                'receiver_city': 'Chicago',
                'origin_branch': created_branches['NYC-01'],
                'destination_branch': created_branches['ORD-01'],
                'current_branch': created_branches['NYC-01'],
                'delivery_type': 'DOORSTEP',
                'service_type': 'STANDARD',
                'category': 'APPAREL',
                'item_description': 'Set of 3 Italian Wool Winter Trench Coats with garment protectors',
                'weight_kg': 5.50,
                'length_cm': 50.0,
                'width_cm': 40.0,
                'height_cm': 15.0,
                'is_fragile': False,
                'declared_value': 890.00,
                'status': 'RECEIVED_AT_ORIGIN',
                'payment_status': 'PAID',
                'payment_method': 'MOBILE_MONEY',
                'assigned_courier': None,
                'created_by': staff_nyc,
                'logs': [
                    ('BOOKED', created_branches['NYC-01'], 'New York Midtown Hub', 'Registered online by customer and drop-off barcode generated.', -12),
                    ('RECEIVED_AT_ORIGIN', created_branches['NYC-01'], 'New York Midtown Hub', 'Package received at front reception desk and verified.', -3),
                ]
            },
            {
                'tracking_number': 'PRCL-202610-559102',
                'security_otp': '330198',
                'sender_name': 'Key West Coffee Roasters',
                'sender_phone': '+1 (305) 555-7722',
                'sender_email': 'order@kwroasters.com',
                'sender_address': '500 Duval St',
                'sender_city': 'Miami',
                'sender_user': None,
                'receiver_name': 'Lucas Scott',
                'receiver_phone': '+1 (310) 555-6612',
                'receiver_email': 'lscott@sunsetcafe.la',
                'receiver_address': '8400 Sunset Blvd',
                'receiver_city': 'Los Angeles',
                'origin_branch': created_branches['MIA-01'],
                'destination_branch': created_branches['LAX-01'],
                'current_branch': created_branches['MIA-01'],
                'delivery_type': 'DOORSTEP',
                'service_type': 'STANDARD',
                'category': 'PERISHABLE',
                'item_description': 'Fresh Roasted Espresso Beans (10 x 1kg hermetic vacuum foil packs)',
                'weight_kg': 10.50,
                'length_cm': 45.0,
                'width_cm': 30.0,
                'height_cm': 25.0,
                'is_fragile': False,
                'declared_value': 280.00,
                'status': 'BOOKED',
                'payment_status': 'COD',
                'payment_method': 'COD',
                'assigned_courier': None,
                'created_by': admin_user,
                'logs': [
                    ('BOOKED', created_branches['MIA-01'], 'Miami Station', 'Cash on Delivery (COD) parcel registered by sender.', -2),
                ]
            }
        ]

        now = timezone.now()
        for p_info in parcels_mock:
            logs = p_info.pop('logs')
            parcel_obj, _ = Parcel.objects.update_or_create(
                tracking_number=p_info['tracking_number'],
                defaults=p_info
            )
            parcel_obj.calculate_pricing()
            if parcel_obj.status == 'DELIVERED':
                parcel_obj.delivered_at = now - datetime.timedelta(hours=1)
                parcel_obj.received_by_name = 'Sarah Connor'
            parcel_obj.save()

            # clear existing logs and insert chronological tracking logs
            parcel_obj.tracking_logs.all().delete()
            for st, branch, loc, act, offset_hours in logs:
                log_time = now + datetime.timedelta(hours=offset_hours)
                ParcelTrackingLog.objects.create(
                    parcel=parcel_obj,
                    status=st,
                    branch=branch,
                    location_name=loc,
                    activity=act,
                    notes='System scan event recorded.',
                    updated_by=admin_user,
                    created_at=log_time
                )
        self.stdout.write(self.style.SUCCESS(f'{len(parcels_mock)} Parcels with tracking histories seeded.'))

        # 5. Transit Manifest
        manifest_obj, _ = TransitManifest.objects.update_or_create(
            manifest_number='MNF-202610-00101',
            defaults={
                'origin_branch': created_branches['NYC-01'],
                'destination_branch': created_branches['ORD-01'],
                'driver_name': 'David Miller',
                'driver_phone': '+1 (555) 928-1122',
                'vehicle_plate': 'FL-Semi-9912',
                'status': 'DISPATCHED',
                'dispatched_at': now - datetime.timedelta(hours=10),
                'notes': 'Overnight linehaul run via Interstate 80 East-to-West corridor.',
                'created_by': staff_nyc,
            }
        )
        p1 = Parcel.objects.filter(tracking_number='PRCL-202610-829104').first()
        p5 = Parcel.objects.filter(tracking_number='PRCL-202610-338192').first()
        if p1:
            manifest_obj.parcels.add(p1)
        if p5:
            manifest_obj.parcels.add(p5)
        self.stdout.write(self.style.SUCCESS('Transit manifests seeded.'))

        # 6. Pickup Requests
        PickupRequest.objects.update_or_create(
            request_number='REQ-202610-001',
            defaults={
                'customer_name': 'TechCorp Solutions HQ',
                'customer_phone': '+1 (212) 555-8811',
                'customer_email': 'logistics@techcorp.io',
                'pickup_address': '350 5th Ave, Suite 3300',
                'pickup_city': 'New York',
                'preferred_date': now.date() + datetime.timedelta(days=1),
                'preferred_time_slot': 'MORNING',
                'estimated_weight_kg': 8.5,
                'package_description': '3 boxes of returned monitor brackets and test laptops.',
                'branch': created_branches['NYC-01'],
                'assigned_courier': rider_alex,
                'status': 'ASSIGNED',
                'notes': 'Please call building security desk on arrival.'
            }
        )
        PickupRequest.objects.update_or_create(
            request_number='REQ-202610-002',
            defaults={
                'customer_name': 'Elena Rostova',
                'customer_phone': '+1 (310) 555-4422',
                'customer_email': 'elena.rostova@designstudio.la',
                'pickup_address': '1200 S Grand Ave',
                'pickup_city': 'Los Angeles',
                'preferred_date': now.date(),
                'preferred_time_slot': 'AFTERNOON',
                'estimated_weight_kg': 2.0,
                'package_description': 'Architecture blueprint rolls and fabric samples.',
                'branch': created_branches['LAX-01'],
                'assigned_courier': None,
                'status': 'PENDING',
                'notes': 'Door code is #4092'
            }
        )
        self.stdout.write(self.style.SUCCESS('Pickup requests seeded.'))

        # 7. Customer Inquiries
        CustomerInquiry.objects.update_or_create(
            ticket_number='TCK-100842',
            defaults={
                'name': 'James Sterling',
                'email': 'customer@example.com',
                'phone': '+1 (212) 555-0199',
                'tracking_number': 'PRCL-202610-829104',
                'subject': 'Estimated delivery time window for Los Angeles destination',
                'message': 'Hello, I shipped a laptop yesterday under express delivery. Could you verify if it will arrive by tomorrow noon?',
                'status': 'IN_PROGRESS',
                'staff_reply': 'Hello James, our records indicate your consignment has completed intermediate sorting in Chicago and is scheduled on flight FL-801 to LAX tonight. Expected delivery window is tomorrow between 10:00 AM and 1:00 PM.',
                'replied_by': staff_nyc,
            }
        )
        CustomerInquiry.objects.update_or_create(
            ticket_number='TCK-100843',
            defaults={
                'name': 'Arthur Dent',
                'email': 'arthur@galaxy.org',
                'phone': '+1 (312) 555-4321',
                'tracking_number': '',
                'subject': 'Corporate bulk shipping rate discount inquiry',
                'message': 'We are looking to partner for 200+ monthly shipments between Chicago and New York. Can we schedule a call with your business account manager?',
                'status': 'OPEN',
                'staff_reply': '',
                'replied_by': None,
            }
        )
        self.stdout.write(self.style.SUCCESS('Customer inquiries seeded.'))

        self.stdout.write(self.style.SUCCESS(
            '\n============================================================\n'
            '  SWIFTPARCEL SEED DATA SUCCESSFULLY GENERATED!\n'
            '============================================================\n'
            'Demo Accounts created:\n'
            ' - Administrator:  admin / admin123\n'
            ' - Branch Staff:   staff_nyc / staff123 (New York Hub)\n'
            ' - Branch Staff:   staff_lax / staff123 (Los Angeles Hub)\n'
            ' - Courier Rider:  rider_alex / rider123 (New York Scooter)\n'
            ' - Courier Rider:  rider_sam / rider123 (LA Van)\n'
            ' - Customer:       customer1 / customer123\n'
            '============================================================\n'
        ))
