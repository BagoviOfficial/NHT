# Multi-Tenant SaaS Architecture & Operations Guide

## 1. Executive Summary

The **Multi-Tenant SaaS Extension** transforms the Parcel Management System into an enterprise software-as-a-service (SaaS) platform. A single installation hosts multiple independent courier and transport organizations (tenants), each with:

- Isolated staff accounts and role-based permissions (RBAC)
- Distinct consignment tracking prefixes (e.g. `NHT-XXXXXXXX`, `TWK-XXXXXXXX`)
- Custom origin terminals, destination routes, and pricing
- Customized 80mm thermal receipt branding and terms
- Independent landscape A4 daily waybill PDF statements
- Dedicated dynamic form field and dropdown choices
- Customized brand color themes (primary and accent colors dynamically injected)
- Tiered subscription quotas (Starter, Professional, Enterprise)

Platform Owners control the entire multi-tenant ecosystem from the unified **SaaS Master Dashboard** (`/saas/`), with 1-click client provisioning, real-time KPI aggregates, live portal impersonation/switching, and CSV exports.

---

## 2. Multi-Tenant Architectural Pattern

The platform implements a **Shared Database with Discriminator Column (`tenant_id`)** pattern. This offers maximum operational efficiency, simplified database backups, seamless cross-client analytics for platform owners, and rapid onboarding without the overhead of maintaining individual PostgreSQL schemas or separate database servers.

```
                              ┌──────────────────────────────────────────────┐
                              │            Incoming HTTP Request             │
                              └──────────────────────┬───────────────────────┘
                                                     │
                                                     ▼
                                      ┌──────────────────────────────┐
                                      │       TenantMiddleware       │
                                      └──────────────┬───────────────┘
                                                     │
               ┌─────────────────────────────────────┴─────────────────────────────────────┐
               ▼                                     ▼                                     ▼
      1. Platform Owner Switch               2. Authenticated User                 3. Host Header
      (Active session client)                (user.tenant FK)                      (subdomain or custom domain)
               │                                     │                                     │
               └─────────────────────────────────────┬─────────────────────────────────────┘
                                                     │
                                                     ▼
                                      ┌──────────────────────────────┐
                                      │    request.tenant Resolved   │
                                      └──────────────┬───────────────┘
                                                     │
                ┌────────────────────────────────────┼────────────────────────────────────┐
                ▼                                    ▼                                    ▼
       Parcels & Line Items                  Users & Permissions                  Routes & Settings
    (Scoped by parcel.tenant)               (Scoped by user.tenant)             (Scoped by route.tenant)
```

### Key Models with Tenant Isolation
- **`Tenant`** (`tenants.models`): Central organization entity holding name, slug, subdomain, custom domain, tracking prefix, currency, hotline, branding colors, subscription plan, and operational limits.
- **`User`** (`accounts.models`): Scoped via `tenant = ForeignKey(Tenant, null=True, blank=True)`. Global platform administrators have `tenant=None` and `is_superuser=True`.
- **`Route`** (`routes.models`): Scoped via `tenant = ForeignKey(Tenant)`. Unique route names per tenant.
- **`Parcel`** (`parcels.models`): Scoped via `tenant = ForeignKey(Tenant)`. Tracking numbers are prefixed with the tenant's prefix (`{tenant.tracking_prefix}-{random_8}`).
- **`AuditLog`** (`audit.models`): Records `tenant = ForeignKey(Tenant)`. Client admins only see their own audit log, while platform owners can audit the entire system.
- **`SiteSettings`**, **`FieldConfig`**, **`ChoiceConfig`** (`core.models`): Each tenant maintains their own configuration overrides.

---

## 3. Subscription Tiers & Operational Limits

| Tier | Staff Limit (`max_users`) | Route Limit (`max_routes`) | Public Rate Limit | Description |
| :--- | :---: | :---: | :---: | :--- |
| **Starter** | 10 | 10 | 30 req/min | Small regional courier or single-route operator |
| **Professional** | 50 | 50 | 60 req/min | Medium inter-county bus and logistics enterprise |
| **Enterprise** | 500 | 500 | 120 req/min | Large multi-fleet national transporter |

### Automatic Quota Enforcement
1. **Staff Account Creation**: `accounts/views.py` validates `tenant.users.count() < tenant.max_users`. If quota is reached, the administrator is prevented from creating new staff accounts until upgrading.
2. **Route Configuration**: `routes/views.py` validates `tenant.routes.count() < tenant.max_routes`.
3. **Quota Visualization**: Visual progress bars in the SaaS Master Dashboard display quota utilization percentages in real time.

---

## 4. White-Label Theming & Dynamic Branding

Each client organization can configure their brand identity:
- **`primary_color`** (default `#0d47a1`): Controls top navbar backgrounds, primary buttons, and report headers.
- **`accent_color`** (default `#ff8f00`): Controls highlights, active navigation accents, and secondary badges.
- **`receipt_header`** & **`receipt_footer`**: Printed on 80mm thermal receipts alongside the safe tracking QR code.
- **`currency`**: ISO currency code (KES, USD, TZS, UGX, etc.) automatically formatted across booking forms, manifests, receipts, and dashboards.

In `templates/base.html`, dynamic CSS `:root` variables inject the tenant's brand palette:
```css
:root {
  --nht-primary: {{ ACTIVE_TENANT.primary_color|default:"#0d47a1" }};
  --nht-accent: {{ ACTIVE_TENANT.accent_color|default:"#ff8f00" }};
  --nht-dark: {{ ACTIVE_TENANT.primary_color|default:"#1a237e" }};
  --nht-light: #f8fafc;
}
```

---

## 5. Security & Cross-Tenant Data Isolation (Anti-IDOR)

Multi-tenant SaaS security requires defense-in-depth across the entire stack:

1. **Object-Level Authorization**: `can_user_access_parcel(user, parcel)` checks that `user.tenant == parcel.tenant`.
2. **Form Filtering**: `UserCreateForm`, `UserUpdateForm`, and `ParcelForm` strictly scope route querysets to `Route.objects.filter(tenant=tenant, is_active=True)`.
3. **Action Endpoints**: Dispatch, arrival, collection, cancellation, and admin override verify object ownership before executing state changes.
4. **Audit Log Privacy**: Client Super Admins are restricted to audit logs matching `tenant=request.tenant`. Global platform owners see all events.
5. **Suspension Enforcement**: When a client status is set to `SUSPENDED` or `is_active=False`, `TenantMiddleware` immediately denies access with HTTP 403.

---

## 6. CLI Management Commands

### 1. Provision Tenant via CLI
```bash
python3 manage.py provision_tenant \
    --name "Coastline Express Logistics" \
    --slug "coastline" \
    --prefix "CBC" \
    --head-office "Mombasa" \
    --currency "KES" \
    --plan "PROFESSIONAL" \
    --admin-username "coastline_admin" \
    --admin-phone "0711223344" \
    --admin-email "admin@coastline.co.ke" \
    --primary-color "#00695c" \
    --accent-color "#ffb300" \
    --routes "Malindi, Kilifi, Lamu, Voi"
```

### 2. Create Global Platform Super Admin
```bash
python3 manage.py create_platform_admin \
    --username "saas_owner" \
    --password "SecureOwnerPassword123!" \
    --phone "0700000001" \
    --email "owner@platform.com"
```

---

## 7. SaaS Master Dashboard Operations

Access `/saas/` as a Global Platform Super Admin (`is_superuser=True, tenant=None`):

1. **KPI Aggregates**: Total installed clients, active/trial/suspended breakdown, global consignment count, and gross shipping revenue.
2. **Install Client Wizard** (`/saas/install/`): 1-screen automated provisioning with auto-generated passwords, default categories, and starter routes.
3. **Workspace Switcher** (`/saas/switch/<tenant_id>/`): Launch into any client portal to test and manage operations as that client.
4. **Client Details** (`/saas/clients/<slug>/`): View client staff rosters, routes, recent consignments, and quota meters.
5. **Client Configuration** (`/saas/clients/<slug>/edit/`): Update quotas, branding colors, receipt templates, and rates.
6. **Client Suspension / Activation**: 1-click toggle to suspend access or reactivate.
7. **CSV Roster Export** (`/saas/export/csv/`): Download a full spreadsheet of all clients, tiers, and metrics.
8. **Safe Client Deletion** (`/saas/clients/<slug>/delete/`): Permanent removal requiring typing the exact company name to prevent accidents.
