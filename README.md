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
python manage.py migrate
python manage.py runserver
```

Health check: <http://localhost:8000/api/health/>

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
