# TASFUED Secure Electronic Voting System (EVS)

> **Project:** Design and Implementation of a Secure Electronic Voting System Using Cryptographic Techniques for Student Union Elections
> **Institution:** Tai Solarin Federal University of Education (TASFUED), Ijebu-Ode, Ogun State
> **Student Researcher:** Alabi Kayode Emmanuel — Matric No. 20220204224
> **Supervisor:** Dr. Ogunbanwo

---

## Quick Start (Development)

```bash
# 1. Clone and enter the project
cd evoting

# 2. Create a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — at minimum change SECRET_KEY

# 5. Seed demo data (optional)
python scripts/seed.py

# 6. Run
python run.py
```

Open [http://localhost:5000](http://localhost:5000)

**Default admin credentials** (change immediately):
- Matric: `ADMIN001`
- Password: `Admin@1234`

**Demo voter credentials** (after seeding):
- Matric: `20220204221`
- Password: `Voter@1234`

---

## Architecture

Three-tier layered architecture:

```
Presentation  →  Jinja2 + Tailwind CSS + Alpine.js + GSAP
Application   →  Flask routes (thin) → Services → Repositories
Data          →  SQLAlchemy ORM → SQLite (dev) / PostgreSQL (prod)
```

### Project Structure

```
evoting/
├── app/
│   ├── __init__.py          # App factory
│   ├── config.py            # Dev / Testing / Production configs
│   ├── extensions.py        # db, login_manager, csrf, bcrypt, limiter
│   ├── scheduler.py         # APScheduler: auto open/close elections
│   ├── models/              # SQLAlchemy models (User, Election, Ballot, …)
│   ├── services/            # Business logic (AuthService, BallotService, …)
│   ├── repositories/        # Data-access layer
│   ├── routes/              # Flask blueprints (public, auth, voter, admin, …)
│   ├── templates/           # Jinja2 templates
│   ├── static/              # CSS, JS, images
│   └── utils/               # Decorators, helpers
├── tests/
│   ├── unit/                # CryptoService, AuthService, BallotService
│   └── integration/         # Full lifecycle via test client
├── scripts/seed.py          # Demo data seeder
├── keys/                    # Election private keys (gitignored)
├── Dockerfile
├── docker-compose.yml
└── nginx/nginx.conf
```

---

## Security Model

| Layer | Implementation |
|---|---|
| Ballot confidentiality | RSA-2048 OAEP / SHA-256 (PyCryptodome) |
| Ballot integrity | SHA-256 hash over `voter_ref‖election_id‖timestamp‖ciphertext` |
| Password storage | bcrypt, work factor 12, unique salt per user |
| Session security | HttpOnly, Secure, SameSite=Lax cookies, 30-min idle timeout |
| CSRF protection | Flask-WTF tokens on every mutating request |
| RBAC | Three roles: Admin, Voter, Auditor — enforced via decorators |
| Audit trail | Append-only `audit_log` table; no UPDATE/DELETE routes |
| Transport | HTTPS/TLS via Nginx (production) |
| Rate limiting | Flask-Limiter on `/login`, `/register`, `/vote` |

---

## Running Tests

```bash
# All tests
python -m pytest

# With coverage report
python -m pytest --cov=app --cov-report=term-missing

# Crypto unit tests only
python -m pytest tests/unit/test_crypto_service.py -v

# Integration tests only
python -m pytest tests/integration/ -v
```

---

## Docker (Production)

```bash
# Copy and configure environment
cp .env.example .env
# Fill in: SECRET_KEY, DB_PASSWORD, ADMIN_DEFAULT_PASSWORD

# Build and start
docker-compose up -d

# View logs
docker-compose logs -f web
```

---

## Election Lifecycle

```
DRAFT → SCHEDULED → OPEN → CLOSED → TALLIED → PUBLISHED
```

1. **DRAFT** — Admin creates election, adds candidates, imports voter CSV
2. **SCHEDULED** — Locked; scheduler auto-opens at `start_at`
3. **OPEN** — Eligible voters can cast ballots
4. **CLOSED** — Auto-closed at `end_at`; voting ends
5. **TALLIED** — Admin uploads private key; system decrypts + verifies all ballots
6. **PUBLISHED** — Results visible publicly

---

## API Endpoints

| Method | Route | Auth | Purpose |
|---|---|---|---|
| GET | `/api/elections` | Public | List elections |
| GET | `/api/elections/{id}/results` | Public (published only) | Results breakdown |
| GET | `/api/elections/{id}/status` | Voter | Has this voter voted? |
| GET | `/api/elections/{id}/turnout` | Admin | Live turnout stats |
| POST | `/auth/login` | Public | Authenticate |
| POST | `/auth/register` | Public (roster-gated) | Register voter |
| POST | `/voter/ballot/{id}/submit` | Voter | Cast encrypted ballot |
| POST | `/admin/elections/{id}/tally` | Admin | Run tally |

Full docs at `/api/docs` (when running with `apiflask`).

---

*Derived from the approved research paper "Design and Implementation of a Secure Electronic Voting System Using Cryptographic Techniques for Student Union Elections" — Alabi Kayode Emmanuel, Supervisor: Dr. Ogunbanwo, May 2026.*
