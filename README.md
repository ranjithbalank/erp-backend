# erp-backend

Backend API for the multi-tenant ERP (SaaS). Python 3.12 + Django 5.x + Django REST
Framework, per `TDR-001` (frozen stack). See the BRD / `CLAUDE.md` for the binding
architecture and security rules.

> ⚠️ Security is the product. Tenant isolation, server-side access control, the
> super-admin wall, secure-by-default, and financial integrity are non-negotiable.
> Read `CLAUDE.md` before contributing.

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Framework | Django 5.x + Django REST Framework |
| Auth | JWT (simplejwt) + MFA (TOTP), FIDO2 for admins |
| Database | PostgreSQL 16 (SQLite for local dev only) |
| Multi-tenancy | django-tenants (schema-per-tenant) |

## Getting started (local)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # then edit values
python manage.py migrate_schemas --shared   # set up the public schema
python manage.py runserver
```

Health check: <http://localhost:8000/api/health/>

## Multi-tenancy (Phase 0)

Schema-per-tenant via [`django-tenants`](https://django-tenants.readthedocs.io)
(TDR-001). **Requires PostgreSQL** — `DATABASE_URL` must point at a Postgres
server (SQLite is not supported). The tenant is resolved from the request
**hostname** by `TenantMainMiddleware` and is never taken from request
body/params (RULE #1 — tenant isolation is a security boundary).

- `SHARED_APPS` live in the `public` schema (platform registry of tenants).
- `TENANT_APPS` are created fresh inside each tenant's own schema.

Create a tenant + domain:

```python
from tenants.models import Client, Domain
t = Client.objects.create(schema_name="acme", name="Acme Inc")   # creates schema
Domain.objects.create(domain="acme.localhost", tenant=t, is_primary=True)
```

Then reach it at `http://acme.localhost:8000/`. Any `*.localhost` host is allowed
in local dev (see `ALLOWED_HOSTS`).

## Modules

### Access control — `accesscontrol` (MOD-SEC-001)

| Requirement | Status |
|---|---|
| DEP-01/02/03 departments (CRUD, unique code+name, hierarchy) | ✅ |
| DEP-05 block delete/deactivate with active employees | ✅ |
| DEP-06 employee count per department | ✅ |
| DEP-04 department head | ⏳ (optional; deferred) |
| DEP-07 audit-log changes | ⏳ pending audit foundation |
| EMP-01 register employee (personal/job/department) | ✅ |
| EMP-02 assign department + designation | ✅ |
| EMP-06 HR-only employee (no user account) | ✅ |
| EMP-03/04/05/07/08/09 user provisioning & invites | ⏳ next unit |

**Departments API** (auth required; tenant resolved from host):

| Method | Path | Notes |
|---|---|---|
| GET | `/api/departments/` | list; `?search=`, `?is_active=true`, `?ordering=code`; includes `employee_count` |
| POST | `/api/departments/` | `{code, name, description?, parent?}` — code normalised to UPPER |
| GET/PATCH/PUT | `/api/departments/{id}/` | retrieve / update |
| DELETE | `/api/departments/{id}/` | **soft-delete**; blocked if active employees (DEP-05) |
| POST | `/api/departments/{id}/activate/` · `/deactivate/` | toggle active |

**Employees API** (auth required):

| Method | Path | Notes |
|---|---|---|
| GET | `/api/employees/` | list; `?search=`, `?department=<id>`, `?is_active=true` |
| POST | `/api/employees/` | `{employee_code, first_name, last_name, designation, department, work_email?, phone?, employment_type?, date_of_joining?}` |
| GET/PATCH/PUT | `/api/employees/{id}/` | retrieve / update |
| DELETE | `/api/employees/{id}/` | **soft-delete** (sets `is_active=false`) |
| POST | `/api/employees/{id}/activate/` · `/deactivate/` | toggle active |

## Branching model

Code flows **up** through four long-lived environments. You never push directly to
`prod` or `test`; changes arrive there by promoting a green branch via Pull Request.

```
feature/module branch ──PR──▶ dev1 ──PR──▶ dev2 ──PR──▶ test ──PR──▶ prod
   (your work)              (integration)  (QA dev)   (staging)  (production)
```

| Branch | Purpose |
|---|---|
| `dev1` | Active development / integration. **Default branch** — open module & phase PRs here. |
| `dev2` | Second dev/integration stage. |
| `test` | QA / staging validation. |
| `prod` | Production. Release-only. |

## Per-module / per-phase workflow

Per `CLAUDE.md` §5: **one module or one phase at a time**, keyed to requirement IDs
(e.g. `DEP-01`, `USR-02`).

1. Branch off `dev1`: `git checkout dev1 && git pull && git checkout -b feature/<module-or-phase>`
2. Implement the requirement ID (data model + migrations → DRF API → tests).
3. Add/Update docs for the module under `docs/` and update this README if needed.
4. Run `/security-review`; fix any HIGH/CRITICAL.
5. Open a **Pull Request into `dev1`** using the PR template. Promotions up the chain
   (`dev1`→`dev2`→`test`→`prod`) are also PRs.

See `.github/pull_request_template.md` for the required checklist.
