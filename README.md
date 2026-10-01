# SwiftParcel Express — Parcel Management System (PMS)

A comprehensive, enterprise-grade **Parcel & Logistics Management System** built with **Django 6.1** and **PostgreSQL 18**.

Designed for courier companies, logistics providers, and parcel delivery networks with multi-hub routing, linehaul transit manifests, courier rider portals with OTP verification, scannable QR/barcodes, and real-time shipment tracking.

---

## 🚀 Key Features

### 1. Multi-Tier Role-Based Architecture
- **HQ Administrators & Managers**: Full oversight, system KPIs, financial reports, branch management, rate matrix configuration.
- **Branch Staff / Operators**: Consignment booking, weighing & dimension scanning, intake verification, linehaul manifest dispatching and receiving.
- **Couriers & Delivery Riders**: Dedicated mobile-optimized portal, assigned parcel deliveries queue, doorstep handover confirmation with **6-digit recipient Security OTP verification**, and failed attempt logging.
- **Customers & Clients**: Public tracking console, booking history, invoice & waybill receipt downloads, doorstep courier pickup requests, support inquiry ticketing.

### 2. Consignment & Parcel Operations
- **Unique Tracking Code Generation**: Auto-allocates standardized alphanumeric codes (e.g., `PRCL-202610-829104`).
- **Dynamic Pricing Calculator**: Automatic pricing based on actual weight, volumetric dimensional weight `(L x W x H) / 5000`, fragile handling surcharges, declared value cargo insurance, and state/VAT tax.
- **Automated Handover OTP**: Auto-generates a secure 6-digit confirmation PIN for the recipient to safeguard delivery handoffs.
- **Printable Waybill Labels & Official Receipts**:
  - Vector SVG Code 128 Barcodes
  - Scannable QR Codes (base64 SVG data URLs, no heavy Pillow dependencies required)
  - Clear sender/recipient sections, fragile indicators, and recipient signature lines
  - Print-optimized CSS (`@media print`) for thermal and A4 printers.

### 3. Linehaul & Transit Manifests
- Group multiple consignments into a single transit vehicle/truck trip between logistics hubs.
- **1-Click Dispatch**: Automatically updates all contained parcels to `IN_TRANSIT` with tracking event logs.
- **1-Click Receive**: Destination hub marks arrival, updating all parcels to `RECEIVED_AT_DESTINATION`.

### 4. Real-Time Consignment Tracking
- Milestone visual stepper (Accepted &rarr; In Sorting &rarr; In Transit &rarr; Destination Hub &rarr; Out for Delivery &rarr; Delivered).
- Chronological, timestamped event audit trail with location names and operator activity descriptions.

### 5. Doorstep Pickup Requests & Support Helpdesk
- Customers can request couriers to pick up packages from home or office.
- Customer support ticket system with staff replies.

---

## 🗄️ PostgreSQL Database Schema

The database backend is **PostgreSQL** (`parcel_db`), with the following key models:

| Model | Description |
| :--- | :--- |
| `Branch` | Logistics hubs, regional distribution centers, and local pickup offices. |
| `UserProfile` | User extension for roles (`ADMIN`, `BRANCH_STAFF`, `COURIER`, `CUSTOMER`), branch affiliation, and vehicle details. |
| `ShippingRate` | Pricing matrix for Standard Ground, Express Air, and Same-Day Priority. |
| `Parcel` | Core consignment model with sender, receiver, dimensions, status, OTP, and pricing. |
| `ParcelTrackingLog` | Immutable chronological movement audit trail for every parcel event. |
| `TransitManifest` | Consolidated linehaul manifests linking multiple parcels to drivers and vehicles. |
| `PickupRequest` | On-demand customer doorstep pickup bookings. |
| `CustomerInquiry` | Support tickets with customer questions and staff replies. |

---

## 👤 Pre-Configured Demo Accounts

Run `python manage.py seed_data` to populate these ready-to-test accounts:

| Role | Username | Password | Notes |
| :--- | :--- | :--- | :--- |
| **Administrator (HQ)** | `admin` | `admin123` | Full access across all hubs, revenue, and settings |
| **Branch Staff (NYC)** | `staff_nyc` | `staff123` | New York Midtown Central Hub |
| **Branch Staff (LAX)** | `staff_lax` | `staff123` | Los Angeles Pacific Gateway Hub |
| **Courier Rider** | `rider_alex` | `rider123` | Assigned to NYC Hub (Honda PCX Scooter) |
| **Courier Rider** | `rider_sam` | `rider123` | Assigned to LAX Hub (Ford Transit Van) |
| **Customer** | `customer1` | `customer123` | Sender / Recipient client account |

> **Tip:** The login page features **1-Click Demo Buttons** that instantly fill credentials for any role.

---

## 📦 Sample Tracking Numbers to Explore

- `PRCL-202610-829104` — **In Transit** (Dell XPS Laptop & Dock, NYC &rarr; LAX)
- `PRCL-202610-449120` — **Out for Delivery** (Legal Contracts, assigned to Rider Alex)
- `PRCL-202610-110294` — **Ready for Branch Pickup** (Ceramic Urn, Fragile, at Miami Hub)
- `PRCL-202610-771239` — **Delivered** (Priority Medical Equipment, verified with OTP)

---

## 🛠️ Installation & Setup Guide

### 1. Start PostgreSQL Service
```bash
# Start the PostgreSQL daemon
pg_ctl -D $PREFIX/var/lib/postgresql -l $PREFIX/var/lib/postgresql/server.log start

# Check status
pg_isready
```

### 2. Install Python Dependencies
```bash
pip install django psycopg qrcode tzdata
```

### 3. Run Migrations & Seed Database
```bash
python manage.py makemigrations parcels
python manage.py migrate
python manage.py seed_data
```

### 4. Run the Development Server
```bash
python manage.py runserver 0.0.0.0:8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 🧪 Running Automated Tests

Run the comprehensive test suite verifying calculations, barcode/QR generation, OTP security, and manifest workflows:

```bash
python manage.py test
```

---

## 🔌 Asynchronous REST APIs

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/calculate-rate/` | `GET` | Calculate shipping cost on the fly given weight, dimensions, fragile flag, and service tier. |
| `/api/quick-track/<tracking_number>/` | `GET` | Returns instant JSON summary of parcel progress, status, and route. |
