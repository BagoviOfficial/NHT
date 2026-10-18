MASTER PROMPT — BUILD NORTHERN HIGHWAYS TRANSPORTERS PARCEL MANAGEMENT SYSTEM

You are an expert Django software architect, senior Python developer, PostgreSQL engineer and application security engineer.

Build a production-ready Parcel Management System for:

NORTHERN HIGHWAYS TRANSPORTERS

The system is a Kenyan bus-parcel/courier management platform. It must be implemented using Django 5.x, PostgreSQL and Django's built-in security and authentication mechanisms wherever possible.

The uploaded project specification is the functional baseline. Preserve its business requirements while improving the architecture, security, RBAC, validation, auditability and maintainability described below.

The uploaded specification establishes Nairobi as the head-office origin, destination routes including Garissa, Wajir, Kotulo Drop-off, Elwak, Rhamu, Lafey, Arabia and Mandera, and the public/staff application split.

---

1. PRIMARY OBJECTIVE

Build a complete Django web application that allows authorised staff to:

- register parcels;
- generate unique tracking numbers;
- record sender and receiver information;
- add multiple shipment items;
- automatically calculate parcel charges;
- record payment status and payment method;
- assign trucks and drivers;
- dispatch parcels;
- track parcel movement;
- record arrival at destination;
- manage collection;
- print 80mm thermal receipts with a QR code containing the parcel tracking URL;
- generate daily A4 PDF statements;
- search and filter shipments;
- maintain a complete audit trail;
- expose a safe public tracking interface;
- allow authorised administrators to configure routes, form fields, choices and company settings.

The system must be secure by design.

DO NOT implement security merely as an afterthought.

---

2. TECHNOLOGY STACK

Use:

- Python 3.12+
- Django 5.x
- PostgreSQL
- psycopg
- Django ORM
- Django Templates
- Bootstrap 5
- Vanilla JavaScript
- HTML5
- CSS3
- WeasyPrint or xhtml2pdf for PDF generation
- A QR-code generation library such as "qrcode" with Pillow, or an equivalent maintained package, for receipt QR codes
- django-environ or equivalent environment configuration
- django-axes or a carefully implemented equivalent for authentication brute-force protection
- django-ratelimit or equivalent for sensitive/public endpoints
- Django's built-in password hashing
- Django permissions and Groups
- Django sessions
- Django messages framework
- Django cache framework
- pytest-django or Django's TestCase framework

Avoid React, Vue or other frontend frameworks.

Do not introduce unnecessary third-party dependencies.

Every dependency must have a clear reason.

---

3. PROJECT ARCHITECTURE

Use a clean modular Django architecture.

Suggested applications:

config/
core/
accounts/
routes/
parcels/
audit/
reports/

Use a clear separation between:

- models
- forms
- services
- selectors/query logic
- views
- URLs
- templates
- permissions
- validators
- management commands
- tests

Do not put complex business logic directly inside templates.

Do not put important authorisation logic only inside JavaScript.

The server must remain authoritative.

---

4. DATABASE

Production database:

PostgreSQL.

Configuration must come exclusively from environment variables.

Example:

DB_NAME
DB_USER
DB_PASSWORD
DB_HOST
DB_PORT

Never hard-code database credentials.

Never commit ".env" files.

Provide:

.env.example

Document PostgreSQL setup in README.

SQLite may exist only as an explicitly documented offline development fallback.

Production configuration must never silently fall back to SQLite.

Use:

- proper indexes;
- unique constraints;
- foreign-key constraints;
- check constraints where appropriate;
- transactions;
- "select_related";
- "prefetch_related";
- database-level integrity wherever practical.

---

5. CUSTOM USER MODEL

Create the custom user model from the beginning.

Use:

class User(AbstractUser):

Required:

- username
- first name
- last name
- phone
- email
- active status
- staff status
- superuser status

Phone number must be unique.

Use:

AUTH_USER_MODEL = "accounts.User"

Do not attempt to replace the user model later in development.

---

6. RBAC — ROLE BASED ACCESS CONTROL

Implement proper Django Groups and Permissions.

Do NOT rely only on:

is_staff
is_superuser

Create explicit roles.

Minimum roles:

SUPER ADMIN

Full system administration.

Can:

- manage users;
- activate/deactivate users;
- assign roles;
- reset passwords;
- manage routes;
- manage configuration;
- manage form fields;
- manage dropdown choices;
- manage company settings;
- manage currency;
- view reports;
- view audit logs;
- correct authorised records;
- perform administrative overrides according to configuration.

OPERATIONS MANAGER

Can:

- view all shipments;
- create shipments;
- edit eligible shipments;
- update shipment statuses;
- dispatch shipments;
- manage collection;
- view reports;
- print receipts;
- generate daily statements.

Cannot:

- manage users;
- modify security configuration;
- modify RBAC;
- modify system-wide configuration.

COUNTER / FRONT DESK STAFF

Can:

- create parcels;
- edit parcels before dispatch;
- view parcels;
- print receipts;
- search tracking numbers;
- perform permitted collection operations.

Cannot:

- manage users;
- manage routes;
- modify system configuration;
- access audit administration.

DISPATCH / TRANSPORT STAFF

Can:

- view assigned operational shipments;
- update permitted dispatch statuses;
- enter truck and driver information;
- view relevant shipment details.

Should not be able to modify financial information unless explicitly granted.

DESTINATION / COLLECTION STAFF

Can:

- view parcels destined for their assigned branch/route;
- mark arrival;
- mark parcels awaiting collection;
- complete collection;
- record collector information.

They must not automatically receive access to every parcel in the system.

REPORTING / READ ONLY

Can:

- view permitted reports;
- search permitted records;
- generate/read reports.

Cannot:

- create;
- edit;
- delete;
- dispatch;
- collect;
- modify configuration.

---

7. OBJECT-LEVEL AUTHORISATION

RBAC must be combined with object-level restrictions.

Do NOT assume that:

user.has_perm("parcels.view_parcel")

automatically means the user can see every parcel.

Implement branch/route-aware authorisation.

For example:

- destination staff should normally see parcels assigned to their branch;
- route staff should only modify operational data relevant to their role;
- users should not access objects simply by changing an ID in the URL.

Every detail/edit/update/collection endpoint must verify:

1. authentication;
2. Django permission;
3. role;
4. object ownership/scope;
5. parcel state;
6. operation-specific permission.

Example:

/shipments/123/

must NOT expose parcel 123 merely because the user guessed the URL.

Prevent IDOR/BOLA vulnerabilities.

Use UUIDs where useful for public/internal object references, but do not rely on UUIDs as the security mechanism. Authorisation must still be enforced.

---

8. PARCEL DATA MODEL

Implement:

Parcel

Fields:

- tracking_number
- route
- truck_plate_number
- driver_name
- sender_name
- sender_phone
- receiver_name
- receiver_phone
- receiver_id_number
- payment_status
- payment_method
- status
- price
- created_by
- collected_by_name
- collected_at
- created_at
- updated_at

Do NOT add parcel weight.

Tracking format:

NHT-XXXXXXXX

where XXXXXXXX is eight uppercase alphanumeric characters.

Tracking numbers must be:

- unique;
- cryptographically/randomly generated;
- collision-safe;
- indexed.

Do not use predictable sequential tracking numbers.

---

9. SHIPMENT ITEMS

Each parcel must contain one or more items.

ShipmentItem:

- parcel
- description
- wrap_type
- quantity
- unit_price

Calculate:

line_total = quantity × unit_price

Parcel total:

SUM(all line totals)

Use Decimal.

Never use floating-point arithmetic for money.

Use database transactions when saving a parcel and its item formset.

Prevent negative or zero prices where business rules prohibit them.

Prevent zero or negative quantities.

Validate maximum sensible values to prevent abuse.

---

10. PARCEL STATUS MACHINE

Implement a central service responsible for status transitions.

Statuses:

RECEIVED_AT_HQ
IN_TRANSIT
ARRIVED_AT_DESTINATION
AWAITING_COLLECTION
COLLECTED
CANCELLED

Allowed transitions:

RECEIVED_AT_HQ
    -> IN_TRANSIT
    -> CANCELLED

IN_TRANSIT
    -> ARRIVED_AT_DESTINATION
    -> CANCELLED

ARRIVED_AT_DESTINATION
    -> AWAITING_COLLECTION
    -> CANCELLED

AWAITING_COLLECTION
    -> COLLECTED
    -> CANCELLED

COLLECTED
    -> terminal

CANCELLED
    -> terminal

Never trust a status supplied by the browser.

Validate every transition server-side.

If moving to:

IN_TRANSIT

require:

- truck plate number;
- driver name.

Create a ParcelStatusHistory record for every successful transition.

Record:

- old status;
- new status;
- timestamp;
- user;
- note;
- IP address where appropriate.

---

11. EDITING RULES

Normal staff may edit a shipment only while:

RECEIVED_AT_HQ

Once dispatched, ordinary staff must not modify the core shipment data.

Superuser editing after dispatch may be enabled/disabled through SiteSettings.

However, administrative modifications after dispatch must:

- require explicit authorisation;
- generate an audit record;
- record the old value;
- record the new value;
- identify the administrator;
- record timestamp;
- record reason.

Never silently overwrite important historical information.

---

12. AUDIT LOGGING

Create a dedicated audit application.

Log security-sensitive and business-critical events including:

- login;
- failed login;
- logout;
- password reset;
- user creation;
- user deactivation;
- role changes;
- permission changes;
- parcel creation;
- parcel modification;
- status changes;
- cancellation;
- collection;
- administrative overrides;
- configuration changes;
- route changes;
- payment changes;
- report generation where appropriate.

Audit entries should contain, where appropriate:

- actor;
- action;
- object type;
- object identifier;
- timestamp;
- IP address;
- user agent;
- old values;
- new values;
- reason/note.

Audit records must not be editable by normal staff.

Do not expose sensitive audit information publicly.

Never log:

- passwords;
- password hashes;
- session cookies;
- authentication tokens;
- API secrets;
- complete payment credentials.

---

13. PUBLIC TRACKING SECURITY

Public tracking:

/

/track/<tracking_number>/

Must expose only safe information.

Public tracking may show:

- tracking number;
- destination;
- current status;
- status timeline;
- relevant dates/times.

NEVER expose publicly:

- price;
- payment status;
- payment method;
- receiver ID number;
- private staff notes;
- internal user information;
- audit information;
- driver personal phone number;
- sensitive sender/receiver information beyond what is genuinely required.

Tracking lookup must be:

- case-insensitive;
- exact-match;
- rate-limited;
- resistant to enumeration.

Do not implement wildcard searching on the public tracking endpoint.

Add throttling/rate limiting.

Return generic errors so attackers cannot easily distinguish whether arbitrary identifiers exist.

The QR code printed on receipts must point only to the safe public tracking URL and must not encode private parcel data, payment details or internal identifiers.

---

14. AUTHENTICATION SECURITY

Implement secure authentication.

Requirements:

- Django password hashing;
- strong password validation;
- login throttling;
- failed-login monitoring;
- secure session cookies;
- HttpOnly cookies;
- SameSite protection;
- Secure cookies in production;
- session expiry;
- logout support;
- password-change support;
- password-reset support;
- CSRF protection.

Never create insecure default credentials in production.

If demo credentials are created by "seed_demo", make this explicit:

DEVELOPMENT / DEMO ONLY

Require an environment flag such as:

CREATE_DEMO_ADMIN=true

Never silently create:

admin / admin123

in production.

---

15. SECURITY HEADERS

Production settings must support:

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SECURE_HSTS_SECONDS
SECURE_HSTS_INCLUDE_SUBDOMAINS
SECURE_HSTS_PRELOAD
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY
X_FRAME_OPTIONS = "DENY"

Configure these appropriately for development versus production.

Do not blindly enable HTTPS redirects in local development.

Add a documented deployment configuration.

---

16. XSS PROTECTION

Use Django's template autoescaping.

Never use:

|safe

unless content is explicitly sanitised and trusted.

Admin-configurable text such as:

- receipt header;
- receipt footer;
- about text;
- help text;

must be handled safely.

If HTML is permitted in future, sanitise it with an appropriate allowlist.

Do not render arbitrary database content as raw HTML.

---

17. SQL INJECTION

Use Django ORM.

Do not concatenate user input into SQL.

If raw SQL is absolutely necessary:

- use parameterised queries;
- document why;
- test it.

Search/filter functionality must safely handle arbitrary user input.

---

18. CSRF

All state-changing browser requests must use CSRF protection.

This includes:

- create;
- edit;
- status change;
- cancellation;
- collection;
- user management;
- route management;
- configuration;
- password changes.

Do not disable CSRF middleware.

Do not create unsafe GET endpoints.

GET requests must not mutate state.

---

19. INPUT VALIDATION

Validate on the server.

Client-side validation is only a usability enhancement.

Validate:

- names;
- phone numbers;
- ID numbers;
- tracking numbers;
- truck registration numbers;
- driver names;
- quantities;
- unit prices;
- payment values;
- route IDs;
- status transitions;
- uploaded data if uploads are later introduced.

Use Django Forms and ModelForms.

Do not trust:

- hidden fields;
- disabled fields;
- JavaScript-calculated totals;
- URL IDs;
- submitted role names;
- submitted user IDs.

---

20. DYNAMIC FORM CONFIGURATION

Implement:

FieldConfig

and:

ChoiceConfig

as specified.

The superuser must be able to configure:

- label;
- placeholder;
- help text;
- required;
- visible;
- order;
- active;
- dropdown values;
- default choices.

However:

SECURITY RULE:

Dynamic configuration must NEVER allow an administrator to create arbitrary executable Python, template code, SQL, JavaScript or HTML.

Configuration is DATA, not CODE.

Whitelist allowed field keys.

Do not allow FieldConfig to dynamically execute arbitrary field classes.

Every configured field must map to a predefined safe server-side field.

---

21. ROUTES

Initial routes:

- Garissa
- Wajir
- Kotulo Drop-off
- Elwak
- Rhamu
- Lafey
- Arabia
- Mandera

Administrators may add routes through the UI.

Routes must use:

- unique names;
- unique slugs;
- active/inactive status.

Do not hard-delete routes already referenced by parcels.

Use protected foreign keys or soft deactivation.

---

22. PAYMENT SECURITY

Payment statuses:

PAID
COD
UNPAID

Payment methods:

CASH
MPESA

Do not store:

- M-Pesa PINs;
- bank passwords;
- full card details;
- authentication secrets.

If M-Pesa integration is added later, isolate it into a dedicated service.

Never trust a client-side payment-success flag.

Payment confirmation must originate from a trusted server-side integration or authorised staff workflow.

Financial corrections must be audited.

---

23. RECEIPTS

Create an 80mm thermal receipt.

Use print CSS:

@page {
    size: 80mm auto;
    margin: 0;
}

Receipt must include:

- company name;
- receipt header;
- date/time;
- tracking number;
- a QR code linking to the safe public tracking URL;
- route;
- sender;
- receiver;
- items;
- quantities;
- unit prices;
- line totals;
- final price;
- payment status;
- payment method;
- truck;
- driver;
- receipt footer.

The QR code must be generated server-side, rendered in the dedicated receipt template, and remain readable when printed at 80mm width. Provide suitable alt text or a visible tracking URL for accessibility and scanners that cannot read the code.

Do not expose internal audit information.

Use a dedicated print template.

---

24. DAILY A4 STATEMENT

Create:

/statements/daily/

Generate an A4 report containing:

- selected date;
- shipment count;
- tracking numbers;
- sender;
- receiver;
- route;
- item count;
- driver;
- truck;
- payment status;
- amount;
- route subtotals;
- final totals.

Totals:

- number of shipments;
- gross total;
- PAID total;
- COD total;
- UNPAID total.

Calculate totals server-side.

Do not trust values submitted from the browser.

---

25. DASHBOARD

Dashboard should show authorised information according to role.

Possible metrics:

- today's shipments;
- parcels in transit;
- awaiting collection;
- COD outstanding;
- recent shipments.

Do not expose financial information to roles that should not see it.

Use permission-aware queries.

Avoid N+1 database queries.

---

26. SEARCH

Staff shipment search should support:

- tracking number;
- sender name;
- receiver name;
- sender phone;
- receiver phone;
- status;
- route.

Use pagination.

Set sensible maximum page sizes.

Do not perform expensive unrestricted wildcard queries against huge datasets.

Use database indexes where appropriate.

---

27. ADMIN PANEL

Create a secure custom administration area:

/admin-panel/

with:

/admin-panel/users/
/admin-panel/settings/
/admin-panel/config/
/routes/

Every administration endpoint must perform explicit server-side authorisation.

Do not rely on hiding navigation links.

A non-authorised user directly requesting an administrative URL must receive HTTP 403 or an appropriate secure response.

Django "/admin/" remains available as a secondary administration interface.

---

28. USER MANAGEMENT

Super Admin can:

- create users;
- deactivate users;
- change roles;
- assign branch/route;
- reset passwords;
- view last-login information.

Prevent:

- privilege escalation;
- users granting themselves permissions;
- normal staff assigning superuser;
- normal staff modifying their own role.

Do not allow a superuser to accidentally remove their own final administrative access without an explicit safety mechanism.

---

29. PRIVACY

Treat sender/receiver information as sensitive operational data.

Minimise public exposure.

Use least privilege.

Do not display full receiver ID numbers unnecessarily.

Mask sensitive values where appropriate.

Do not expose personal information through:

- public tracking;
- predictable URLs;
- error messages;
- logs;
- debug pages;
- PDF metadata.

Production:

DEBUG = False

Never expose Django debug pages publicly.

---

30. ERROR HANDLING

Implement custom:

400
403
404
500

pages.

Do not expose:

- Python tracebacks;
- SQL queries;
- filesystem paths;
- environment variables;
- secrets;
- stack traces.

Use structured application logging.

Separate:

- security logs;
- application logs;
- audit logs.

---

31. SECRETS MANAGEMENT

Never hard-code:

- SECRET_KEY;
- database password;
- API keys;
- SMTP passwords;
- M-Pesa credentials;
- cloud credentials.

Use environment variables.

Generate:

.env.example

with placeholders only.

Add:

.env

to ".gitignore".

Also ignore:

- database dumps;
- local media;
- local logs;
- virtual environments;
- Python cache;
- IDE configuration.

---

32. FILE UPLOAD SECURITY

There are currently no mandatory user file uploads.

Do not introduce upload functionality unless required.

If uploads are later introduced, implement:

- extension allowlisting;
- MIME validation;
- size limits;
- random filenames;
- storage outside executable paths;
- malware scanning where appropriate;
- authenticated access;
- content-disposition controls.

---

33. PERFORMANCE

Use:

- database indexes;
- "select_related";
- "prefetch_related";
- pagination;
- aggregation queries;
- caching for configuration;
- cache invalidation when configuration changes.

Do not cache user-specific sensitive data globally.

Do not leak one user's authorised data to another through shared caching.

---

34. TRANSACTIONS

Use:

transaction.atomic()

for multi-step operations such as:

- creating a parcel and its items;
- changing status and creating history;
- collection;
- administrative corrections;
- user/role changes where multiple database records are involved.

Ensure failed operations roll back completely.

---

35. CONCURRENCY

Protect critical operations from race conditions.

For status transitions:

- retrieve the parcel safely;
- lock the row where necessary;
- verify current state;
- perform transition;
- create history;
- commit atomically.

Prevent two staff members from simultaneously collecting the same parcel.

Prevent duplicate tracking numbers.

Prevent conflicting status transitions.

---

36. BUSINESS LOGIC SERVICES

Create service-layer functions/classes such as:

create_parcel()
update_parcel()
calculate_parcel_total()
transition_parcel_status()
collect_parcel()
generate_daily_statement()

Do not duplicate critical business rules across multiple views.

Views should orchestrate services rather than contain all business logic.

---

37. PUBLIC/STUDENT-FRIENDLY UI

Use clean Bootstrap 5 UI.

The public homepage should include:

- company name;
- tracking search;
- explanation of parcel tracking;
- support information;
- feature cards.

Staff dashboard should be practical for counter/transport operations.

Use clear status badges.

Use confirmation dialogs for:

- cancellation;
- collection;
- administrative overrides.

Do not rely on colour alone to communicate status.

---

38. FOOTER

Every page, including printable pages where appropriate, must contain:

Powered by BAGOVI TECHNOLOGIES — https://bagovi.com/

Do not allow arbitrary users to modify this credit.

---

39. MANAGEMENT COMMAND

Create:

python manage.py seed_demo

Demo data must NOT run automatically in production.

Create an explicit environment/configuration guard.

The seed command may create:

- demo routes;
- demo choices;
- demo configuration;
- demo users;
- demo shipments.

If creating a demo superuser, require an explicit development flag.

Never deploy default credentials silently.

---

40. TESTING REQUIREMENTS

Write comprehensive automated tests.

Minimum test categories:

Authentication

- unauthenticated users cannot access staff pages;
- invalid credentials are rejected;
- brute-force protection works;
- inactive users cannot authenticate.

RBAC

Test every role.

Verify:

- permissions;
- route/branch restrictions;
- administrative restrictions;
- privilege escalation prevention;
- direct URL access;
- object-level authorisation.

Parcel

- creation;
- tracking number generation;
- duplicate prevention;
- item totals;
- validation;
- editing rules.

Status machine

Test every valid transition.

Test every invalid transition.

Test terminal states.

Test dispatch requirements.

Collection

Test:

- correct collection;
- duplicate collection prevention;
- receiver verification;
- timestamp;
- collector.

Security

Test:

- CSRF;
- IDOR/BOLA;
- XSS;
- injection;
- unauthorised configuration access;
- privilege escalation;
- unsafe redirects;
- public tracking enumeration;
- rate limiting.

Reports

Test:

- daily report;
- date filtering;
- totals;
- COD;
- PAID;
- UNPAID;
- PDF generation.

Configuration

Test:

- dynamic labels;
- required fields;
- hidden fields;
- ordering;
- choice configuration;
- server-side validation;
- cache invalidation.

Receipts

Test:

- 80mm receipt rendering;
- QR code generation;
- QR code target URL;
- absence of private payment and audit data from the QR payload;
- receipt access permissions.

---

41. SECURITY TESTING

Where practical, add automated checks for common OWASP risks:

- Broken Access Control;
- Identification and Authentication Failures;
- Injection;
- Security Misconfiguration;
- Cross-Site Scripting;
- Insecure Design;
- Logging/Monitoring Failures;
- SSRF where applicable;
- CSRF;
- IDOR/BOLA;
- privilege escalation.

Do not claim the application is "100% secure".

The README should state that security is implemented according to recognised secure-development practices but requires proper infrastructure configuration, patching and operational security.

---

42. DEPENDENCY MANAGEMENT

Create:

requirements.txt

Pin versions appropriately.

Do not blindly install packages.

Before finalising:

- inspect dependencies;
- remove unnecessary dependencies;
- ensure packages are actively maintained where practical;
- document why security-sensitive packages are used.

---

43. CODE QUALITY

Use:

- PEP 8;
- type hints where useful;
- meaningful function names;
- docstrings for important services;
- small reusable functions;
- clear module boundaries.

Avoid:

- duplicated logic;
- giant views;
- giant models;
- hard-coded business rules;
- magic numbers;
- hidden side effects.

---

44. README

Create a comprehensive README containing:

1. Project overview
2. Architecture
3. Requirements
4. PostgreSQL installation
5. Environment variables
6. Installation
7. Migrations
8. Demo seed
9. Running development server
10. Running tests
11. Production deployment
12. Security configuration
13. RBAC model
14. Parcel lifecycle
15. Printing, including 80mm thermal receipt QR-code behaviour
16. PDF generation
17. Backup recommendations
18. Updating dependencies
19. Troubleshooting

Include exact commands.

---

45. DEVELOPMENT WORKFLOW

Implement the system incrementally.

Follow this order:

PHASE 1

Project scaffold.

Implement:

- Django project;
- PostgreSQL;
- environment configuration;
- custom User;
- base templates;
- security settings.

Run migrations and tests.

PHASE 2

Accounts and RBAC.

Implement:

- Groups;
- permissions;
- roles;
- route/branch restrictions;
- login;
- logout;
- password management.

Write tests.

PHASE 3

Core and configuration.

Implement:

- SiteSettings;
- FieldConfig;
- ChoiceConfig;
- dynamic forms;
- configuration UI.

Write tests.

PHASE 4

Routes.

Implement:

- Route model;
- CRUD;
- permissions;
- route restrictions.

Write tests.

PHASE 5

Parcels.

Implement:

- Parcel;
- ShipmentItem;
- ParcelStatusHistory;
- formsets;
- totals;
- tracking number;
- status machine.

Write tests.

PHASE 6

Audit.

Implement:

- audit models;
- audit services;
- security events;
- business events.

Write tests.

PHASE 7

Operations.

Implement:

- dispatch;
- arrival;
- awaiting collection;
- collection;
- cancellation.

Write tests.

PHASE 8

Printing and reports.

Implement:

- thermal receipt;
- QR-code generation and safe public tracking URL;
- A4 daily statement;
- HTML print version;
- totals.

Write tests.

PHASE 9

Public tracking.

Implement:

- homepage;
- tracking;
- about/support;
- rate limiting;
- privacy controls.

Write tests.

PHASE 10

Hardening.

Run:

- migrations;
- Django system checks;
- test suite;
- linting;
- dependency checks where available;
- security checks.

Fix every high-severity issue.

PHASE 11

Final verification.

Run the complete application from a clean environment.

---

46. ACCEPTANCE CRITERIA

The application is NOT complete until all of the following work:

1. PostgreSQL configuration works.
2. Custom User works.
3. RBAC works.
4. Object-level authorisation works.
5. Privilege escalation is prevented.
6. Staff cannot access admin-only functions.
7. Public users cannot access staff functions.
8. Tracking numbers are unique.
9. Parcels can contain multiple items.
10. Totals are calculated correctly.
11. Editing is blocked after dispatch.
12. Dispatch requires truck and driver.
13. Illegal status transitions are rejected.
14. Every status transition creates history.
15. Collection cannot occur twice.
16. Public tracking never reveals financial information.
17. Public tracking is rate-limited.
18. Receipts print correctly at 80mm.
19. Receipts include a readable QR code linking to the safe public tracking URL.
20. QR codes do not contain private parcel or payment data.
21. Daily statements generate correctly at A4.
22. Route management works.
23. Dynamic field configuration works.
24. Dynamic choice configuration works.
25. Configuration cannot execute arbitrary code.
26. Currency changes are reflected dynamically.
27. Audit logging works.
28. Authentication security works.
29. CSRF protection works.
30. Secure session configuration works.
31. Production debug mode is disabled.
32. Secrets are environment-based.
33. Database transactions protect critical operations.
34. Race conditions around status/collection are handled.
35. Automated tests pass.
36. Django system checks pass.
37. README is complete.
38. No critical/high-severity security issue remains unresolved.

---

47. IMPORTANT AGENT BEHAVIOUR

You are an autonomous software engineering agent.

Do not merely describe the implementation.

Actually create the files and implement the application.

Before modifying files:

- inspect the existing project;
- preserve useful existing work;
- identify missing components;
- avoid destructive changes unless necessary.

After every major phase:

1. run tests;
2. inspect failures;
3. fix failures;
4. run Django checks;
5. continue only when the phase is stable.

Do not hide errors.

Do not claim something works without testing it.

Do not mark acceptance criteria as complete unless you actually verify them.

When you encounter an ambiguity, prefer:

1. the uploaded NHT specification;
2. explicit business rules in this prompt;
3. Django security best practices;
4. least-privilege principles;
5. maintainable architecture.

Do not invent business functionality unnecessarily.

---

48. FINAL SECURITY REVIEW

Before declaring the project complete, perform a dedicated security review.

Create:

SECURITY.md

Document:

- authentication model;
- RBAC model;
- authorisation boundaries;
- sensitive data;
- audit logging;
- security headers;
- CSRF;
- rate limiting;
- database security;
- secret management;
- backup considerations;
- incident response considerations;
- known limitations.

Also create:

docs/ARCHITECTURE.md

and:

docs/RBAC.md

and:

docs/PARCEL_LIFECYCLE.md

The final response from the coding agent must contain:

- implemented features;
- project structure;
- database design summary;
- RBAC summary;
- security controls;
- tests executed;
- test results;
- Django checks;
- remaining limitations, if any;
- exact commands required to run the system.

DO NOT claim production readiness if security or acceptance tests are failing.

START IMPLEMENTATION NOW.
