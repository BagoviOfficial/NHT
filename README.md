# Northern Highways Transporters — Parcel Management System (PMS)

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x%20%7C%206.x-green.svg)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%2B%20%7C%2018%2B-blue.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](#)

A secure, production-ready bus-parcel and courier logistics web application engineered for **Northern Highways Transporters (NHT)**. The platform powers inter-county cargo booking, fleet dispatch, transit tracking, destination collection, thermal receipt printing, and daily consignment manifest reporting across Kenya's northern transport corridor.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Requirements](#3-requirements)
4. [PostgreSQL Installation & Setup](#4-postgresql-installation--setup)
5. [Environment Variables](#5-environment-variables)
6. [Installation & Setup](#6-installation--setup)
7. [Running Migrations](#7-running-migrations)
8. [Demo Data Seeding](#8-demo-data-seeding)
9. [Running the Development Server](#9-running-the-development-server)
10. [Running the Automated Test Suite](#10-running-the-automated-test-suite)
11. [Production Deployment](#11-production-deployment)
12. [Security Configuration](#12-security-configuration)
13. [Role-Based Access Control (RBAC)](#13-role-based-access-control-rbac)
14. [Consignment Lifecycle & State Machine](#14-consignment-lifecycle--state-machine)
15. [80mm Thermal Receipt Printing & Vector SVG QR Codes](#15-80mm-thermal-receipt-printing--vector-svg-qr-codes)
16. [Daily A4 PDF Consignment Manifest Generation](#16-daily-a4-pdf-consignment-manifest-generation)
17. [Multi-Tenant SaaS Operations & Client Provisioning](#17-multi-tenant-saas-operations--client-provisioning)
18. [Database Backup & Recovery Recommendations](#18-database-backup--recovery-recommendations)
19. [Updating Dependencies](#19-updating-dependencies)
20. [Troubleshooting](#20-troubleshooting)

---

## 1. Project Overview

Northern Highways Transporters operates passenger bus and dedicated cargo haulage services connecting the central origin hub in **Nairobi** with transit corridors and frontier destinations:
- **Garissa**
- **Wajir**
- **Kotulo Drop-off**
- **Elwak**
- **Rhamu**
- **Lafey**
- **Arabia**
- **Mandera**

### Core Capabilities
- **Consignment Registration**: Intake multiple items per parcel with descriptions, packaging/wrap types, quantities, and unit prices using exact Decimal arithmetic.
- **Cryptographic Tracking Numbers**: Automatically allocates collision-safe, non-sequential tracking codes in `NHT-XXXXXXXX` format.
- **Fleet & Driver Dispatch**: Restricts consignment dispatch to vehicles with registered registration plate numbers and designated driver names.
- **Destination Station Management**: Regional depot staff can only access, verify, and complete deliveries for consignments bound to their assigned route.
- **Idempotent Collection Handover**: Strictly prevents double-claims and records collector legal identity and timestamps atomically.
- **Public Consignment Tracking**: Rate-limited, exact-match public portal protecting private customer pricing, recipient IDs, and internal remarks.
- **Thermal Receipts & A4 Manifests**: 80mm thermal receipt printing with clean SVG QR codes, alongside automated daily landscape A4 consignment statements.

---

## 2. Architecture

The system utilizes a modular Django architecture with strict separation between HTTP views, input validation forms, business services, authorization selectors, and data models:

```
BAGOVI-NHT/
├── parcel_system/        # Django project root (settings, routing, WSGI/ASGI)
├── tenants/              # Multi-Tenant SaaS core, client provisioning, SaaS dashboard
├── accounts/             # Custom User model, RBAC roles, auth views, lockout
├── routes/               # Inter-county destinations, protected deletion
├── core/                 # Site settings singleton, safe dynamic config, error handlers
├── parcels/              # Consignments, items, FSM transition services, thermal receipts
├── audit/                # Tamper-evident event logging, payload sanitization
├── reports/              # Daily waybill calculations, landscape A4 PDF engine
├── templates/            # Bootstrap 5 responsive templates, print CSS, SaaS dashboard
├── static/               # Assets, stylesheets, vanilla JS scripts
├── docs/                 # In-depth architectural, SaaS, RBAC, and lifecycle documentation
├── requirements.txt      # Pinned production dependencies
└── manage.py             # Administrative CLI
```

For complete architectural and SaaS details, see:
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — System Design & Data Flow
- [docs/SAAS_MULTI_TENANCY.md](docs/SAAS_MULTI_TENANCY.md) — Multi-Tenant SaaS Architecture & Operations Guide
- [docs/RBAC.md](docs/RBAC.md) — Role-Based Access Control Specification
- [docs/PARCEL_LIFECYCLE.md](docs/PARCEL_LIFECYCLE.md) — State Machine & Consignment Lifecycle

---

## 3. Requirements

- **Python**: 3.12 or newer
- **Django**: 5.x or 6.x
- **PostgreSQL**: 16.x, 17.x, or 18.x
- **Web Browser**: Modern standards-compliant browser (Chrome, Edge, Firefox, Safari)

---

## 4. PostgreSQL Installation & Setup

### Ubuntu / Debian Linux
```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib libpq-dev
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

### Termux / Android Linux Environment
```bash
pkg update
pkg install postgresql
mkdir -p $PREFIX/var/lib/postgresql
initdb $PREFIX/var/lib/postgresql
pg_ctl -D $PREFIX/var/lib/postgresql -l $PREFIX/var/lib/postgresql/server.log start
```

### Database & User Provisioning
Open the PostgreSQL command line:
```bash
sudo -u postgres psql
```
Execute the following SQL statements:
```sql
CREATE DATABASE parcel_db;
CREATE USER nht_user WITH PASSWORD 'StrongDatabasePassword2026!';
ALTER ROLE nht_user SET client_encoding TO 'utf8';
ALTER ROLE nht_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE nht_user SET timezone TO 'Africa/Nairobi';
GRANT ALL PRIVILEGES ON DATABASE parcel_db TO nht_user;
\q
```

---

## 5. Environment Variables

Configuration is loaded strictly from environment variables via `django-environ`. Create a local `.env` file from the provided `.env.example`:

```bash
cp .env.example .env
```

### Sample Configuration (`.env`)
```ini
SECRET_KEY=replace-with-a-64-character-cryptographic-secret-key-in-production
DEBUG=False
ALLOWED_HOSTS=northernhighways.co.ke,127.0.0.1,localhost

# Database Configuration (PostgreSQL)
DB_NAME=parcel_db
DB_USER=nht_user
DB_PASSWORD=StrongDatabasePassword2026!
DB_HOST=localhost
DB_PORT=5432

# Production Security Headers (HTTPS)
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# Demo Data Guard
ENABLE_DEMO_SEED=False
CREATE_DEMO_ADMIN=False
```

---

## 6. Installation & Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/bagovi-technologies/northern-highways-pms.git
   cd northern-highways-pms
   ```

2. **Create and Activate a Python Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### Method A: The Famous WordPress-Style 5-Minute Web Installer (Recommended)

The platform features an automated web setup wizard inspired by WordPress's famous 5-minute install:
1. Start the application:
   ```bash
   python manage.py runserver
   ```
2. Open your web browser and navigate to `http://localhost:8000/`.
   - The built-in **`InstallationRedirectMiddleware`** automatically detects uninstalled deployments and redirects all requests directly to `/install/` (or `/setup/`).
   - The wizard runs pre-flight diagnostics (Python runtime, PostgreSQL connectivity, writable storage, and core dependencies).
   - Use the **Live Diagnostics Re-check** and interactive **Database Connection Assistant** to verify and test DB credentials on the fly.
   - Enter your Platform Super Administrator credentials and Primary Courier Enterprise details (tracking prefix, head office, brand theme colors, and starter routes).
   - Click **Run 5-Minute Installation**: the system applies database migrations, establishes the global platform owner, provisions the primary courier organization and routes, records a security audit log, and permanently locks the installer with a `.installed` token.

### Method B: Headless CLI Installation (WP-CLI Equivalent)

For automated Docker containers, CI/CD pipelines, or command-line provisioning:
```bash
python manage.py install_system \
  --platform-title "Northern Highways Transporters — Cloud PMS" \
  --admin-username "platform_admin" \
  --admin-password "Admin@NHT2026!" \
  --admin-email "admin@northernhighways.co.ke" \
  --admin-phone "0700000001" \
  --company-name "Northern Highways Transporters" \
  --tracking-prefix "NHT" \
  --head-office "Nairobi"
```

To reset the installation lock for fresh staging or test re-runs:
```bash
python manage.py reset_installation --confirm
```

---

## 7. Running Migrations

Apply database schema migrations across all modular apps:
```bash
python manage.py migrate
```

Verify that system checks pass without errors:
```bash
python manage.py check
```

---

## 8. Demo Data Seeding

The application includes an environment-guarded management command to initialize default routes, site settings, dynamic form fields, dropdown choices, and demo test accounts:

```bash
python manage.py seed_demo --confirm
```

### Default Seed Accounts (Development & Testing)
| Role | Username | Temporary Password | Scope / Station |
| :--- | :--- | :--- | :--- |
| **Super Admin** | `admin` | `NHTPass2026!` | All Stations & Full System Config |
| **Operations Manager** | `ops_manager` | `NHTPass2026!` | All Consignments & Manifests |
| **Counter Staff** | `counter_clerk` | `NHTPass2026!` | Nairobi Booking Desk |
| **Destination Staff** | `dest_garissa` | `NHTPass2026!` | Scoped to Garissa Depot |
| **Destination Staff** | `dest_mandera` | `NHTPass2026!` | Scoped to Mandera Depot |
| **Dispatch Staff** | `driver_ali` | `NHTPass2026!` | Transport Fleet Assignment |
| **Read Only** | `auditor_sam` | `NHTPass2026!` | Reporting & Oversight |

> [!CAUTION]
> Always change default credentials immediately when deploying to a production or internet-accessible server.

---

## 9. Running the Development Server

Start the Django development server:
```bash
python manage.py runserver 127.0.0.1:8000
```

Access the system in your browser:
- **Public Portal**: `http://127.0.0.1:8000/`
- **Public Tracking**: `http://127.0.0.1:8000/track/`
- **Staff Login**: `http://127.0.0.1:8000/login/`
- **Staff Dashboard**: `http://127.0.0.1:8000/dashboard/`
- **Admin Control Panel**: `http://127.0.0.1:8000/admin-panel/`
- **Secondary Django Admin**: `http://127.0.0.1:8000/admin/`

---

## 10. Running the Automated Test Suite

Execute the comprehensive automated test suite:
```bash
python manage.py test
```

To run tests for an individual application:
```bash
python manage.py test parcels
python manage.py test reports
python manage.py test accounts
```

---

## 11. Production Deployment

### 1. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### 2. Run with Gunicorn Application Server
```bash
pip install gunicorn
gunicorn parcel_system.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 4 \
  --timeout 60 \
  --access-logfile /var/log/nht/access.log \
  --error-logfile /var/log/nht/error.log
```

### 3. Nginx Reverse Proxy Configuration
```nginx
server {
    listen 80;
    server_name northernhighways.co.ke www.northernhighways.co.ke;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name northernhighways.co.ke www.northernhighways.co.ke;

    ssl_certificate /etc/letsencrypt/live/northernhighways.co.ke/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/northernhighways.co.ke/privkey.pem;

    client_max_body_size 10M;

    location /static/ {
        alias /var/www/northern-highways-pms/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location /media/ {
        alias /var/www/northern-highways-pms/media/;
        expires 30d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 12. Security Configuration

For detailed documentation of authentication, IDOR mitigation, session management, and incident response, consult [SECURITY.md](SECURITY.md).

Key safeguards:
- **Authentication**: Lockout protection after 5 failed logins within 15 minutes.
- **Sessions**: `SESSION_COOKIE_HTTPONLY=True`, 8-hour timeout, expire at browser close.
- **Data Privacy**: Public tracking exposes no customer financial data, phone numbers, or national ID details.
- **Dynamic Config**: Strict whitelist validation (`ALLOWED_FIELD_KEYS`); prevents arbitrary template or code execution.

---

## 13. Role-Based Access Control (RBAC)

The application implements granular authorization with branch-level scoping. Consult [docs/RBAC.md](docs/RBAC.md) for the complete permission matrix and selector query implementations.

---

## 14. Consignment Lifecycle & State Machine

Consignments transition through six discrete states:
1. `RECEIVED_AT_HQ`
2. `IN_TRANSIT`
3. `ARRIVED_AT_DESTINATION`
4. `AWAITING_COLLECTION`
5. `COLLECTED` *(Terminal)*
6. `CANCELLED` *(Terminal)*

Detailed state rules and validation requirements are documented in [docs/PARCEL_LIFECYCLE.md](docs/PARCEL_LIFECYCLE.md).

---

## 15. 80mm Thermal Receipt Printing & Vector SVG QR Codes

When booking a consignment, staff can generate an 80mm thermal receipt (`/shipments/<tracking_number>/receipt/`):
- **Thermal Print CSS**: Optimally sized with `@page { size: 80mm auto; margin: 0; }`.
- **Server-Side SVG QR Code**: Rendered in pure vector SVG without dependency on external binary image libraries.
- **Privacy Standard**: Scannable QR code links *strictly* to the safe public tracking URL (`https://northernhighways.co.ke/track/NHT-XXXXXXXX/`). It encodes zero financial or recipient ID records.
- **Human-Readable Fallback**: Displays the full plain text URL directly beneath the QR code for accessibility and damaged barcodes.

---

## 16. Daily A4 PDF Consignment Manifest Generation

Authorized operations managers and super-admins can generate consolidated daily statements (`/statements/daily/`):
- **Route Filtering**: View company-wide totals or isolate specific transit routes.
- **Financial Breakdown**: Server-side computed totals for Gross Consignment, Paid, Cash on Delivery (COD), and Unpaid shipments.
- **Binary PDF Generation**: Direct landscape A4 PDF generation via `fpdf2` (`/statements/daily/pdf/?date=YYYY-MM-DD`).
- **Accounting Format**: Kenyan standard currency formatting (`KES #,##0.00`).

---

## 17. Multi-Tenant SaaS Operations & Client Provisioning

The system includes full SaaS capability, enabling platform owners to install and operate separate courier organizations from a centralized dashboard.

### Accessing the SaaS Master Dashboard
Log in as a Global SaaS Platform Super Admin (`is_superuser=True, tenant=None`) and navigate to:
```
http://127.0.0.1:8000/saas/
```

### Key SaaS Capabilities:
- **1-Click Client Provisioning** (`/saas/install/`): Install a completely isolated organization with auto-generated admin credentials, unique tracking prefix (e.g. `TWK-XXXXXXXX`), custom branding colors, and starter transit routes.
- **Client Workspace Switcher** (`/saas/switch/<id>/`): Launch into any client portal to test and manage operations as that client.
- **Quota & Tier Enforcement**: Automated limits by tier:
  - **Starter**: 10 users / 10 routes
  - **Professional**: 50 users / 50 routes
  - **Enterprise**: 500 users / 500 routes
- **Dynamic White-Label Theming**: Each client's `primary_color` and `accent_color` are dynamically injected into CSS `:root` variables, providing immediate custom branding.
- **Safe Client Deletion** (`/saas/clients/<slug>/delete/`): Permanent removal requiring typing the exact company name to confirm.
- **Client Roster CSV Export** (`/saas/export/csv/`): Download a complete spreadsheet of all tenants, plans, and metrics.

### CLI Management Commands:
```bash
# Provision new client company
python manage.py provision_tenant --name "Coastline Express" --prefix "CBC" --plan "PROFESSIONAL"

# Create global platform administrator
python manage.py create_platform_admin --username "owner" --password "OwnerPassword123!" --phone "0700000001"
```

For comprehensive details, see [docs/SAAS_MULTI_TENANCY.md](docs/SAAS_MULTI_TENANCY.md).

---

## 18. Database Backup & Recovery Recommendations

### Daily Automated Logical Dump
Create a backup script (`/opt/scripts/backup_nht_db.sh`):
```bash
#!/bin/bash
BACKUP_DIR="/secure_backups/postgresql"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
mkdir -p "$BACKUP_DIR"

pg_dump -U nht_user -h localhost -Fc parcel_db > "$BACKUP_DIR/parcel_db_$TIMESTAMP.dump"

# Retain backups for 30 days
find "$BACKUP_DIR" -type f -name "*.dump" -mtime +30 -delete
```

### Restoration from Dump
```bash
pg_restore -U nht_user -h localhost -d parcel_db --clean --if-exists /secure_backups/postgresql/parcel_db_YYYYMMDD_HHMMSS.dump
```

---

## 18. Updating Dependencies

1. Review available package updates:
   ```bash
   pip list --outdated
   ```
2. Test updates in an isolated development environment:
   ```bash
   pip install --upgrade Django psycopg fpdf2 qrcode
   python manage.py check
   python manage.py test
   ```
3. Update pinned versions in `requirements.txt`.

---

## 19. Troubleshooting

### Problem: `FATAL: database "parcel_db" does not exist`
**Resolution**: Run `createdb -U postgres parcel_db` or verify credentials in `.env`.

### Problem: `Character "—" outside range of characters supported` in PDF
**Resolution**: Standard core fonts in `fpdf2` use Latin-1 encoding. Use standard ASCII hyphens (`-`) rather than Unicode em-dashes (`—`) in PDF text cells.

### Problem: Destination Staff cannot see shipments
**Resolution**: Ensure the user has their `assigned_route` configured via `/admin-panel/users/<id>/edit/`. Destination staff are intentionally restricted from seeing consignments outside their branch.

---

## 20. Credits & Copyright

Northern Highways Transporters Parcel Management System is built for Kenyan passenger bus & cargo logistics.

**Powered by [BAGOVI TECHNOLOGIES](https://bagovi.com/)**
