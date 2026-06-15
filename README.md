# OnboardEase HR

**HR Onboarding & Document Management System** — bring new hires through a structured onboarding pipeline, collect and **encrypt** their documents, get **HR manager sign-off**, schedule training and keep a full **audit trail**. Built with **Python · Flask · SQLAlchemy**, with documents encrypted at rest via **AWS S3 + KMS** (or a local envelope-encryption backend for development).

> Stack: **Python · Flask · AWS S3 · AWS KMS** · SQLAlchemy · Jinja2 · vanilla JS

---

## Highlights

| Area | What you get |
| --- | --- |
| **Hiring & onboarding** | A new-hire form (personal info, position, department, start date) that auto-creates a **10-step onboarding checklist** and a pending HR approval. A 7-stage funnel tracks each hire from *Invited → Active*. |
| **Document management** | Upload contracts, IDs, resumes, visas and certificates. Every file is **encrypted at rest** (envelope encryption: a per-file AES-256-GCM data key, wrapped by KMS or a local master key). **Version control** keeps every revision; **downloads are decrypted on the fly and audited**. Expiry tracking flags documents due to lapse. |
| **Approval workflow** | HR managers **e-sign** onboardings and documents (signature name + timestamp + note). Role-based: only `hr_manager`/`admin` can approve. |
| **Training tracker** | Define training modules, schedule sessions (module, date, trainer) per employee, and mark them complete. |
| **Reminders** | A `send-reminders` command (and a dashboard button) e-mails upcoming trainings, expiring documents and pending approvals. The `file` mail backend works with zero SMTP setup. |
| **Audit log** | An immutable record of **who viewed, edited, uploaded, downloaded, approved and deleted** — filterable and CSV-exportable. |
| **Dashboard** | KPIs, onboarding funnel, a **hover-to-reveal** documents-by-type chart, and reminder widgets. |
| **Polish** | **Collapsible sidebar**, a **dark / light theme switcher** (persisted), **resizeable table columns**, and an in-app **system log monitor**. |

---

## Security

- **Encryption at rest** — documents are never stored in the clear. Each file gets a fresh AES-256-GCM data key; that key is wrapped by **AWS KMS** (S3 backend) or a local master key in `data/.master-key` (local backend). SHA-256 is recorded for integrity.
- **Audited access** — every document view/download and every record edit is written to the audit log with actor, action, entity and IP.
- **Auth & roles** — Flask-Login sessions, `werkzeug` password hashing, and `admin / hr_manager / hr_staff` role gates on sensitive actions.
- **CSRF protection** on every form (Flask-WTF). Secrets are read from the environment; `data/` and `.env` are git-ignored.

---

## Getting started

```bash
python -m venv venv
venv\Scripts\activate            # Windows  (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt

copy .env.example .env           # cp on macOS/Linux — then set SECRET_KEY

flask --app run seed             # create tables + demo data (12 hires, encrypted docs)
flask --app run run --port 7474  # http://localhost:7474
# or: python run.py
```

Sign in with **`hr@onboardease.test` / `onboard123`** (admin). Other demo logins: `manager@onboardease.test` (HR manager), `staff@onboardease.test`.

### Switching to AWS S3 + KMS

Set these in `.env` and the storage layer transparently uses S3 + KMS (no app code changes):

```ini
STORAGE_BACKEND=s3
S3_BUCKET=your-onboarding-bucket
AWS_REGION=eu-central-1
KMS_KEY_ID=arn:aws:kms:...:key/....
# AWS credentials via the standard chain (env vars / profile / instance role)
```

### Commands

| Command | Description |
| --- | --- |
| `flask --app run seed` | Drop, recreate and seed the database |
| `flask --app run init-db` | Create tables only |
| `flask --app run send-reminders [--days N]` | Email training / expiry / approval reminders |
| `python run.py` | Dev server on port **7474** |

---

## Architecture

```
OnboardEase HR/
├── run.py / wsgi.py            # entry points
├── config.py                   # env-driven configuration
├── app/
│   ├── __init__.py             # application factory, blueprints, CLI
│   ├── extensions.py           # db, login, csrf
│   ├── models.py               # User, Employee, Document(+Version), Training, Approval, AuditLog, SystemLog…
│   ├── crypto.py               # AES-256-GCM envelope encryption (KMS pattern)
│   ├── storage.py              # LocalBackend (encrypted FS) + S3Backend (S3 + KMS)
│   ├── audit.py · mailer.py · reminders.py · decorators.py · seed.py
│   ├── blueprints/             # auth, dashboard, employees, documents, training,
│   │                           #   approvals, audit_log, system_log
│   ├── templates/              # Jinja2 (base shell + per-feature pages)
│   └── static/                 # css (light+dark tokens) + js (theme, sidebar, table resize, confirm)
└── data/                       # sqlite + encrypted storage + keys + outbox (git-ignored)
```

The **storage and encryption layers are the only code that touches document bytes** — swapping `STORAGE_BACKEND` from `local` to `s3` changes nothing else.

## License

Apache License 2.0.
