# Security Policy & Security Review — Northern Highways Transporters

## 1. Security Overview

Northern Highways Transporters Parcel Management System is designed with **security-by-default** principles. Security controls are enforced at the transport, framework, application service, and database layers.

> [!IMPORTANT]
> While this software is engineered according to secure development best practices and OWASP Top 10 recommendations, maintaining production security requires continuous infrastructure hardening, regular operating system patching, strict TLS certificate maintenance, and rigorous credential management.

---

## 2. Authentication Model

- **Custom Identity Backend**: Built on `accounts.User` extending `AbstractUser` with unique phone numbers.
- **Password Storage**: Uses PBKDF2 with SHA-256 password hashing by default. Test environments use MD5 for execution speed.
- **Brute-Force & Lockout Defense**: Integrated login throttling mechanism tracking consecutive failed login attempts by client IP. After 5 failed attempts within 15 minutes, the IP is locked out.
- **Inactive Account Enforcement**: Deactivated staff members cannot authenticate under any circumstances; attempts to authenticate with matching credentials yield a clear deactivation notice without granting system access.
- **No Insecure Defaults in Production**: The `seed_demo` management command requires an explicit `--confirm` parameter and `ENABLE_DEMO_SEED=True`. Production builds never default to `admin / admin123`.

---

## 3. Role-Based Access Control & Authorization Boundaries

- **Six Explicit Operational Roles**: Super Admin, Operations Manager, Counter Staff, Dispatch Staff, Destination Staff, and Reporting/Read-Only.
- **Object-Level Branch Scoping**: Attendants assigned to a destination station (e.g., Garissa or Mandera) can access *only* consignments bound for their station.
- **IDOR / BOLA Prevention**: Accessing URLs with arbitrary tracking codes (e.g., `/shipments/<tracking_number>/`) executes object-level scope checks via `can_user_access_parcel()`. Unauthorized requests trigger an immediate `PermissionDenied` (HTTP 403).
- **Post-Dispatch Edit Freeze**: Consignments in transit, arrived, awaiting collection, or collected cannot be modified by routine staff. Super Admin overrides require explicit justification and log full before/after diffs in the audit trail.

---

## 4. Sensitive Data Handling & Public Tracking Privacy

- **Data Minimization on Public Tracking**: The public tracking console (`/track/<tracking_number>/`) exposes *strictly operational timeline milestones* (tracking number, destination station, status badges, timestamps).
- **Redacted Public Fields**: The public tracking view never renders shipping charges, payment statuses (PAID/COD), payment methods (CASH/MPESA), recipient national ID numbers, internal staff remarks, or driver personal phone numbers.
- **Exact Match & Rate Limiting**: The public tracking endpoint enforces case-insensitive exact matching with no wildcard searching. Excessive queries from a single client IP trigger an HTTP 429 (Too Many Requests).
- **Thermal Receipt QR Privacy**: The QR code printed on 80mm thermal receipts encodes *only* the public HTTPS tracking URL. It contains no embedded pricing, financial status, or personal identification records.

---

## 5. Audit Logging & Non-Repudiation

- **Dedicated Audit Module**: All security-sensitive and business-critical operations (`LOGIN_SUCCESS`, `LOGIN_FAILED`, `LOGOUT`, `PARCEL_CREATE`, `PARCEL_EDIT`, `STATUS_CHANGE`, `COLLECTION`, `CANCELLATION`, `ADMIN_OVERRIDE`, `SETTINGS_UPDATE`, `ROUTE_CREATE`, `USER_CREATE`) trigger structured `AuditLog` entries.
- **Sensitive Key Sanitization**: Passwords, tokens, PINs, secret keys, and credentials are automatically scrubbed from audit payloads via recursive sanitization (`sanitize_dict()`).
- **Read-Only Audit Trail**: Normal staff have zero access to the audit interface. Audit records cannot be modified or deleted through the application interface.

---

## 6. HTTP & Transport Security Headers

In production mode (`DEBUG=False`), the following headers are configured via environment variables:

| Header / Setting | Configuration | Purpose |
| :--- | :--- | :--- |
| `SECURE_SSL_REDIRECT` | `True` | Forces all HTTP traffic to HTTPS. |
| `SESSION_COOKIE_SECURE` | `True` | Ensures session cookies are transmitted exclusively over HTTPS. |
| `CSRF_COOKIE_SECURE` | `True` | Ensures CSRF tokens are transmitted exclusively over HTTPS. |
| `SESSION_COOKIE_HTTPONLY` | `True` | Blocks JavaScript access to session cookies (XSS mitigation). |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | Prevents browsers from MIME-sniffing away from declared content-type. |
| `X_FRAME_OPTIONS` | `DENY` | Defends against clickjacking across all pages. |
| `SECURE_REFERRER_POLICY` | `same-origin` | Mitigates referrer information leakage. |
| `SECURE_HSTS_SECONDS` | `31536000` (1 year) | Enforces HTTP Strict Transport Security. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` | Extends HSTS to all subdomains. |
| `SECURE_HSTS_PRELOAD` | `True` | Preloads HSTS on modern browser lists. |

---

## 7. CSRF Protection

- All state-changing operations (parcel creation, dispatch, collection, cancellation, user management, route configuration, and password changes) require valid Django CSRF tokens.
- No sensitive operational state is ever mutated via `GET` requests.

---

## 8. Database Security & Injection Prevention

- **Parameterized Queries**: 100% of database queries are executed via the Django ORM, neutralizing SQL injection vectors.
- **Pessimistic Row Locking**: Critical state mutations utilize `select_for_update()` inside `transaction.atomic()` blocks, eliminating race conditions.
- **Environment-Based Credentials**: Database passwords and host details are injected via environment variables; credentials are never hard-coded in source files.

---

## 9. Secret Management

- Secrets (`SECRET_KEY`, database passwords) are stored exclusively in `.env` files that are ignored by version control (`.gitignore`).
- An audited template `.env.example` provides documentation for deployment teams.

---

## 10. Backup & Disaster Recovery Recommendations

1. **PostgreSQL Backups**: Schedule daily automated logical backups using `pg_dump`:
   ```bash
   pg_dump -U postgres -Fc parcel_db > /secure_backup_storage/parcel_db_$(date +%Y%m%d_%H%M%S).dump
   ```
2. **Encrypted Offsite Storage**: Compress and encrypt dumps using GPG or age before transferring to immutable offsite cloud storage.
3. **Backup Restoration Drills**: Perform quarterly restoration validation drills into staging environments to ensure data integrity and RTO/RPO compliance.

---

## 11. Incident Response Procedures

1. **Compromised Staff Account**:
   - Immediately deactivate the affected user via `/admin-panel/users/`.
   - Invalidate active sessions by rotating `SECRET_KEY` or clearing user sessions in the cache.
   - Inspect `/admin-panel/audit/` filtered by the actor to determine historical actions taken.
2. **Brute Force Detection**:
   - Review `/admin-panel/audit/` for `LOGIN_FAILED` spikes.
   - Adjust `tracking_rate_limit_per_minute` in Site Settings if public endpoints are targeted.
   - Blacklist offending IP addresses at the web server (Nginx/Caddy) or Cloudflare firewall layer.

---

## 12. Known Limitations & Future Roadmap

- **External M-Pesa Gateway**: Direct STK-push mobile money integration is currently performed via counter verification rather than an asynchronous webhook endpoint. When Daraja 2.0 API integration is implemented, it should be isolated in a dedicated service with cryptographic HMAC signature verification.
- **Single Master Database**: In multi-region deployments, read-replicas may be considered for high-volume public tracking lookups.
