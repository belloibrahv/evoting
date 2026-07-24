# TASFUED Secure Electronic Voting System (EVS)
## Software Requirements Specification & Implementation Blueprint

**Project:** Design and Implementation of a Secure Electronic Voting System Using Cryptographic Techniques for Student Union Elections
**Institution:** Tai Solarin Federal University of Education (TASFUED), Ijebu-Ode, Ogun State
**Department:** Computer and Information Science, College of Science and Information Technology
**Student Researcher:** Alabi Kayode Emmanuel — Matric No. 20220204224
**Supervisor:** Dr. Ogunbanwo
**Document version:** 1.0 — derived from the approved project research paper
**Document owner:** Engineering implementation team

---

## 0. Purpose of This Document

This document translates the research paper's Chapter 1–4 findings (problem statement, objectives, methodology, cryptographic design, database design) into a buildable, production-grade software specification. It is the single source of truth for implementation: it fixes the technology stack, the architecture, the data model, the API contract, the security control set, and the UI/UX system — including the public **Homepage** — so that engineering work can proceed without ambiguity.

It **preserves every academic requirement already validated in the research** (RSA‑2048/OAEP ballot encryption, SHA‑256 integrity hashing, bcrypt password hashing, three‑role RBAC, audit trail, one‑vote‑per‑voter enforcement) while **modernising the delivery layer** to a "big tech" grade UI/UX — smooth motion, a proper design system, icon packages, CDN‑delivered tooling — without changing the security guarantees the project will be examined on.

---

## 1. Project Summary (from the Research)

Student union elections at TASFUED are currently conducted with paper ballots, which are vulnerable to impersonation, ballot‑box tampering, miscounting, and slow result declaration. This project replaces that process with a web‑based Secure Electronic Voting System that:

- Authenticates voters using their **matriculation number + password**.
- Encrypts every ballot with **RSA‑2048 OAEP (SHA‑256)** before it ever touches storage — plaintext votes are never persisted.
- Stamps every ballot with a **SHA‑256 integrity hash** so any post‑cast tampering is detectable.
- Enforces **Role‑Based Access Control** across three roles: **EC Administrator**, **Voter**, **Results Viewer**.
- Produces a full **audit trail** of authentication, voting, and admin events.
- Issues a **vote receipt** that confirms a vote was recorded without revealing its content.

### 1.1 Goals of This Implementation Phase
1. Ship a deployable system matching the cryptographic and RBAC design validated in the paper.
2. Deliver a **world‑class public Homepage** that presents the project, its problem/solution narrative, security model, and the people behind it (Supervisor + Student Researcher).
3. Deliver application UI (auth, voter, admin, results) built to the same visual/interaction quality bar as major consumer products, with smooth, purposeful motion — not decorative excess.
4. Apply full software engineering discipline: layered architecture, typed data contracts, automated tests, CI, structured logging, documented API, versioned migrations.

### 1.2 Actors
| Role | Description | Key capabilities |
|---|---|---|
| **EC Administrator** | Electoral Commission staff/superuser | Create/configure elections, manage candidates, import/register voters, open/close voting window, view audit trail, run tally & publish results, manage RSA key lifecycle |
| **Voter** | Verified TASFUED student | Authenticate, view ballot, cast exactly one vote per election, receive a vote receipt, view their own voting status |
| **Results Viewer** | Public/student body | View published results only, no write access anywhere |

---

## 2. Functional Requirements

Identifiers use the prefix `FR-xxx`. Each maps to acceptance criteria in §11.

### 2.1 Public Site
- **FR-001** The system shall serve a public **Homepage** (no login required) describing the project, problem, solution, security architecture, and team.
- **FR-002** The Homepage shall present the **Supervisor** (name, title, photo) and the **Student Researcher** (name, matriculation number, photo).
- **FR-003** The Homepage shall link to a public **Results** page (read-only, only shows results after an election is officially published).
- **FR-004** The Homepage shall provide entry points to Voter Login and Admin Login.

### 2.2 Authentication & Account Management
- **FR-010** Users shall authenticate using matriculation number + password.
- **FR-011** Passwords shall be created with a minimum complexity policy (min 8 chars, at least 1 number, 1 letter) and stored as bcrypt hashes (work factor 12).
- **FR-012** The system shall support voter self-registration gated by a pre-loaded eligible-voter roster (matric numbers uploaded by the EC Admin), preventing arbitrary sign-ups.
- **FR-013** The EC Admin shall be able to bulk-import the voter roster via CSV.
- **FR-014** Sessions shall expire after 30 minutes of inactivity; the UI shall show a countdown warning at 25 minutes.
- **FR-015** The system shall support secure password reset via a time-limited, single-use token (email or admin-issued).
- **FR-016** All authentication attempts (success and failure) shall be written to the audit log.

### 2.3 Election Management (EC Admin)
- **FR-020** Admin shall create an election with: title, description, start date/time, end date/time, list of positions (e.g., President, Financial Secretary), and candidates per position.
- **FR-021** Admin shall upload a candidate photo, name, matric number, and manifesto text per candidate.
- **FR-022** Admin shall be able to edit an election only while it is in `DRAFT` status.
- **FR-023** Admin shall be able to transition an election through states: `DRAFT → SCHEDULED → OPEN → CLOSED → TALLIED → PUBLISHED`.
- **FR-024** The system shall automatically transition `SCHEDULED → OPEN` and `OPEN → CLOSED` at the configured timestamps (scheduled job), with a manual override available to the Admin.
- **FR-025** Admin shall generate the election's RSA-2048 key pair at election creation; the public key is stored in the DB, the private key is exported once as an encrypted PEM the Admin must download and store outside the app.
- **FR-026** Admin dashboard shall show live (non-content-revealing) turnout stats — number voted vs. registered — during an OPEN election.

### 2.4 Voting (Voter)
- **FR-030** A voter shall see the ballot only when: they are authenticated, their matric number is on the eligible roster, the election is `OPEN`, and `has_voted = false` for that election.
- **FR-031** The ballot UI shall present one candidate-selection control per position; submission requires an explicit confirm step ("Review your selections") before final submit.
- **FR-032** On submit, the client shall serialize selections to JSON, and the server shall: encrypt with the election's RSA-2048 public key (OAEP/SHA-256), compute the SHA-256 integrity hash over `{anonymised_session_id, election_id, timestamp, ciphertext}`, and persist only the ciphertext + hash.
- **FR-033** The server shall set `has_voted = true` for the voter/election pair inside the same DB transaction as the ballot insert (atomic — no partial state).
- **FR-034** The system shall reject a second vote attempt with a clear, non-revealing message ("You have already voted in this election").
- **FR-035** After a successful vote, the voter shall receive an on-screen and downloadable **vote receipt** containing a receipt ID, timestamp, and ballot hash — never the vote content.
- **FR-036** The ballot casting screen shall disable the submit button after first click (idempotency guard) and the server shall enforce idempotency via a per-request nonce.

### 2.5 Tallying & Results
- **FR-040** Only the EC Admin, holding the election private key, may trigger tallying, after the election reaches `CLOSED`.
- **FR-041** Tallying shall decrypt each ballot, recompute and verify its SHA-256 hash before counting it; mismatches are excluded from the count and flagged in the audit trail for investigation.
- **FR-042** The system shall produce per-position result breakdowns (votes per candidate, percentage, turnout).
- **FR-043** Admin shall explicitly `PUBLISH` results before they become visible to Results Viewers and on the public Homepage results page.
- **FR-044** Published results shall be exportable as PDF/CSV.

### 2.6 Audit Trail
- **FR-050** The system shall log: authentication events, voter registration, election lifecycle transitions, ballot submissions (metadata only), tally runs, hash-verification failures, and admin actions.
- **FR-051** Audit records shall be append-only at the application layer (no update/delete route exists for `audit_log`).
- **FR-052** Admin shall be able to filter/search the audit trail by actor, action type, and date range, and export it as CSV.

### 2.7 Notifications (enhancement over the base paper)
- **FR-060** The system should (optional/stretch) send an email/SMS-style in-app notification when: voting opens, 1 hour remains before close, and results are published.

---

## 3. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-001 | All traffic shall be served over HTTPS/TLS 1.2+ in any non-local environment. |
| NFR-002 | Passwords: bcrypt, work factor 12, never logged or returned in any API response. |
| NFR-003 | CSRF protection on every state-changing request. |
| NFR-004 | Session cookies: `HttpOnly`, `Secure`, `SameSite=Lax`, 30-minute idle expiry. |
| NFR-005 | All DB access via parameterised queries / ORM — no string-built SQL. |
| NFR-006 | Ballot casting page shall render in < 3s on a standard broadband connection (Lighthouse Performance ≥ 90). |
| NFR-007 | System shall correctly handle ≥ 200 concurrent ballot submissions without data corruption (verified via load test). |
| NFR-008 | Homepage shall score ≥ 95 Lighthouse Accessibility and ≥ 90 Best Practices. |
| NFR-009 | UI shall be fully responsive: mobile (360px+), tablet, desktop, and support keyboard-only navigation. |
| NFR-010 | All motion/animation shall respect `prefers-reduced-motion`. |
| NFR-011 | Rate limiting on `/login`, `/register`, `/vote` routes to blunt brute-force and DoS attempts. |
| NFR-012 | Structured JSON logging in production; no PII/plaintext-vote content in logs. |
| NFR-013 | 100% of cryptographic operations (encrypt, hash, verify) covered by automated unit tests. |
| NFR-014 | Codebase maintains ≥ 80% test coverage on the application-logic layer. |

---

## 4. Technology Stack

The stack below **keeps the paper's validated backend and crypto core** (so the academic defence remains accurate) while **substantially upgrading the frontend delivery** to meet the "world-class UI" requirement, using CDN-friendly, no-heavy-build-step tooling that is still trivial to swap for a full Vite/webpack pipeline later if desired.

### 4.1 Backend
| Concern | Choice | Notes |
|---|---|---|
| Language | **Python 3.11** | Matches the research methodology |
| Web framework | **Flask 3.0** | Lightweight, matches the paper |
| ORM | **SQLAlchemy 2.0** | Parameterised queries, migrations via Alembic |
| Auth | **Flask-Login 0.6** | Session-based auth, `login_required` decorators per role |
| CSRF/Forms | **Flask-WTF 1.2** | CSRF tokens on all forms/AJAX |
| Password hashing | **Flask-Bcrypt 1.0** (work factor 12) | |
| Cryptography | **PyCryptodome 3.20** | RSA-2048 OAEP + SHA-256 |
| DB (dev) | **SQLite** | Zero-config local dev |
| DB (prod) | **PostgreSQL 16** | Concurrency-safe for real elections |
| Migrations | **Alembic** | Versioned schema history |
| Background jobs | **APScheduler** (or Celery + Redis at scale) | Auto open/close elections |
| Testing | **Pytest 7.4** + `pytest-cov` | Unit + integration |
| Security scanning | **OWASP ZAP**, `bandit`, `pip-audit` | CI-integrated |
| API docs | **OpenAPI 3.1** via `flask-smorest` or `apiflask` | Auto-generated Swagger UI |

### 4.2 Frontend
The system ships **server-rendered Jinja2 templates** (fast, simple, matches the paper's "no heavy framework" philosophy) **enhanced with a modern component-driven interaction layer**, so there is no separate build pipeline to maintain, yet the UI reads as a polished, animated, big-tech-grade product.

| Concern | Choice | Why |
|---|---|---|
| Markup | HTML5 + Jinja2 templates | Server-rendered, fast first paint, SEO-friendly Homepage |
| Styling | **Tailwind CSS** (via Play CDN in dev / Tailwind CLI build for prod) | Utility-first, enables a tight, consistent design system fast |
| Design tokens | Custom CSS variables layered over Tailwind config | Brand palette, spacing, radii, shadows in one place |
| Interactivity | **Alpine.js 3** (CDN) | Declarative micro-interactions (dropdowns, tabs, modals) without a SPA framework |
| Animation | **GSAP 3** + **ScrollTrigger** (CDN) for cinematic homepage motion; **Motion One** for lightweight micro-interactions in app screens | Smooth, GPU-accelerated, industry-standard (used by Apple, Stripe-style marketing sites) |
| Scroll reveal | **AOS (Animate on Scroll)** or GSAP ScrollTrigger | Section entrance animations on Homepage |
| Icons | **Lucide Icons** (via `lucide` CDN/npm) — primary; **Phosphor Icons** as secondary set | Crisp, consistent, used widely by modern SaaS products |
| Charts | **Chart.js 4** | Turnout graphs, results breakdowns |
| Fonts | **Google Fonts**: `Inter` (UI/body) + `Sora` or `Clash Display`-style geometric sans for display headings | Modern, highly legible, big-tech feel |
| Forms/validation | Native HTML5 validation + light Alpine.js state + server-side WTForms validation (defense in depth) | |
| Toast/notifications | **Notyf** or a small custom Alpine component | Non-blocking feedback |
| PDF export (receipts/results) | **WeasyPrint** (server-side) | Clean, styled PDF generation |
| Build tooling (prod) | Tailwind CLI + `esbuild` for JS bundling/minification | Keeps output small without adopting a full SPA framework |

> **Why not React/Next.js?** A full SPA framework is not necessary for a template-driven, mostly form-and-dashboard application, and it would diverge from the validated architecture in the research paper. The stack above achieves the same "smooth, modern, animated" feel used by large consumer products while staying inside a server-rendered Flask app — lower complexity, faster to secure, faster to defend academically. (If a future iteration wants a full SPA, React + Vite + Framer Motion + shadcn/ui is the natural upgrade path — the API layer below is already REST/JSON so it is swap-compatible.)

### 4.3 Infrastructure & DevOps
| Concern | Choice |
|---|---|
| Reverse proxy | Nginx |
| WSGI server | Gunicorn (multiple workers) |
| Containerisation | Docker + docker-compose (app, db, redis-optional) |
| CI/CD | GitHub Actions: lint → test → security scan → build → deploy |
| Secrets | `.env` (dev) → platform secret manager / environment variables (prod) |
| TLS | Let's Encrypt (Certbot) |
| Key storage (prod target) | AWS KMS / Google Cloud KMS or HSM; PEM+passphrase for the academic prototype |
| Hosting target | Any Linux VPS (Ubuntu 22.04 LTS) — Render/Railway/Fly.io acceptable for demo hosting |
| Monitoring | Sentry (errors) + simple uptime check |

---

## 5. System Architecture

Three-tier architecture, matching and formalising the paper's Figure 3.1:

```
┌──────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                       │
│  Jinja2 templates · Tailwind CSS · Alpine.js · GSAP        │
│  Homepage · Auth screens · Voter app · Admin console        │
└───────────────────────┬──────────────────────────────────┘
                         │ HTTPS (JSON/HTML)
┌───────────────────────▼──────────────────────────────────┐
│  APPLICATION LAYER (Flask)                                │
│  Routing · Session mgmt · RBAC guards · CSRF               │
│  Services: AuthService, ElectionService, BallotService,     │
│            CryptoService, AuditService, TallyService        │
└───────────────────────┬──────────────────────────────────┘
                         │ SQLAlchemy ORM
┌───────────────────────▼──────────────────────────────────┐
│  DATA LAYER                                                │
│  PostgreSQL/SQLite: users, elections, positions, candidates,│
│  ballots, audit_log, sessions                                │
└──────────────────────────────────────────────────────────┘
```

**Design pattern approach (the "big-company" playbook):**
- **MVC-ish layered service architecture** on the backend: routes (controllers) stay thin; all business rules live in a `services/` layer; DB access lives in a `repositories/` layer. This mirrors how large engineering orgs structure monoliths (thin controller → service → repository) for testability.
- **Atomic Design** for frontend components: `tokens → atoms (buttons, inputs, badges) → molecules (form fields, cards) → organisms (navbar, ballot form, results table) → templates → pages`, implemented as Jinja2 macros/partials so components are reused, not copy-pasted.
- **Repository pattern** for data access, **Strategy pattern** for pluggable crypto providers (so RSA can later be swapped for ECC without touching services), **Observer/event pattern** for audit logging (every mutating service call emits an event the `AuditService` subscribes to, so logging can't be forgotten in a new route).
- **Optimistic UI + server-confirmed state** on the ballot flow: instant visual feedback on selection, but the vote is only ever considered "cast" once the server returns the receipt.

---

## 6. Database Schema

Expanded from the paper's five tables into a normalised, production-shaped schema.

```sql
-- USERS
CREATE TABLE users (
    user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    matric_number  VARCHAR(20)  UNIQUE NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    full_name      VARCHAR(100) NOT NULL,
    email          VARCHAR(120),
    photo_url      VARCHAR(255),
    role           VARCHAR(20)  NOT NULL DEFAULT 'voter', -- voter | admin | auditor
    is_active      BOOLEAN      NOT NULL DEFAULT 1,
    created_at     DATETIME     DEFAULT CURRENT_TIMESTAMP
);

-- ELECTIONS
CREATE TABLE elections (
    election_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title           VARCHAR(150) NOT NULL,
    description     TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'draft', -- draft|scheduled|open|closed|tallied|published
    start_at        DATETIME NOT NULL,
    end_at          DATETIME NOT NULL,
    public_key_pem  TEXT NOT NULL,
    created_by       INTEGER REFERENCES users(user_id),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- POSITIONS (contested offices within an election)
CREATE TABLE positions (
    position_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    election_id   INTEGER NOT NULL REFERENCES elections(election_id),
    title         VARCHAR(100) NOT NULL,         -- e.g. "President"
    display_order INTEGER DEFAULT 0
);

-- CANDIDATES
CREATE TABLE candidates (
    candidate_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id   INTEGER NOT NULL REFERENCES positions(position_id),
    full_name     VARCHAR(100) NOT NULL,
    matric_number VARCHAR(20),
    photo_url     VARCHAR(255),
    manifesto     TEXT
);

-- VOTER ROSTER / ELIGIBILITY (per election)
CREATE TABLE eligible_voters (
    eligibility_id INTEGER PRIMARY KEY AUTOINCREMENT,
    election_id    INTEGER NOT NULL REFERENCES elections(election_id),
    matric_number  VARCHAR(20) NOT NULL,
    has_voted      BOOLEAN NOT NULL DEFAULT 0,
    UNIQUE(election_id, matric_number)
);

-- BALLOTS (encrypted; never stores plaintext)
CREATE TABLE ballots (
    ballot_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    election_id          INTEGER NOT NULL REFERENCES elections(election_id),
    anonymised_voter_ref VARCHAR(64) NOT NULL,  -- one-way token, not the user_id
    encrypted_vote_data  TEXT NOT NULL,          -- RSA-OAEP 2048-bit ciphertext, base64
    ballot_hash_sha256   VARCHAR(64) NOT NULL UNIQUE,
    receipt_id           VARCHAR(40) NOT NULL UNIQUE,
    submitted_at         DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- AUDIT LOG (append-only)
CREATE TABLE audit_log (
    log_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER REFERENCES users(user_id),
    action_performed VARCHAR(255) NOT NULL, -- LOGIN_SUCCESS, VOTE_CAST, ELECTION_PUBLISHED...
    ip_address       VARCHAR(45) NOT NULL,
    metadata_json    TEXT,
    timestamp        DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Notes:**
- `ballots.anonymised_voter_ref` is a salted one-way hash of `(user_id, election_id)`, distinct from the audit log's `user_id`, so the system can enforce "already voted" without ever storing a direct link between an identified voter and their ballot content.
- Foreign keys enforced (`PRAGMA foreign_keys=ON` in SQLite; native in Postgres).
- All monetary/PII-free — the schema intentionally stores the minimum data needed.

---

## 7. Cryptographic Design (carried over and formalised from the paper)

1. **Ballot confidentiality — RSA-2048 OAEP/SHA-256** (PyCryptodome). Public key embedded per-election; private key generated once, exported as an admin-held encrypted PEM, never stored inside the app's runtime environment.
2. **Ballot integrity — SHA-256** over `anonymised_voter_ref || election_id || timestamp || ciphertext`. Recomputed and compared at tally time; mismatches are excluded and flagged.
3. **Password security — bcrypt**, work factor 12, unique salt per user.
4. **Session security** — server-side sessions, `HttpOnly`/`Secure`/`SameSite` cookies, 30-minute idle timeout.
5. **CSRF** — Flask-WTF token on every mutating form/AJAX call.
6. **Transport security** — HTTPS/TLS everywhere outside local dev.
7. **Key lifecycle** — prototype: passphrase-protected PEM; production target: AWS/GCP KMS or HSM, key never resident in app memory outside the tally operation window.

---

## 8. REST API Contract (representative)

All endpoints return JSON; all mutating endpoints require a valid CSRF token and, where applicable, an authenticated session with the correct role.

| Method | Route | Role | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | Public (roster-gated) | Voter self-registration |
| POST | `/api/auth/login` | Public | Authenticate, start session |
| POST | `/api/auth/logout` | Any authenticated | End session |
| POST | `/api/auth/password-reset` | Public | Request reset token |
| GET | `/api/elections` | Public | List elections (title/status only, pre-publish) |
| POST | `/api/elections` | Admin | Create election |
| PATCH | `/api/elections/{id}` | Admin | Update election (DRAFT only) |
| POST | `/api/elections/{id}/transition` | Admin | Move lifecycle state |
| POST | `/api/elections/{id}/voters/import` | Admin | Bulk CSV roster import |
| GET | `/api/elections/{id}/ballot` | Voter | Fetch ballot form (positions + candidates) |
| POST | `/api/elections/{id}/vote` | Voter | Submit encrypted ballot → returns receipt |
| GET | `/api/elections/{id}/status` | Voter | Has this voter already voted? |
| POST | `/api/elections/{id}/tally` | Admin | Decrypt + count (requires private key upload) |
| POST | `/api/elections/{id}/publish` | Admin | Publish results |
| GET | `/api/elections/{id}/results` | Public (post-publish) | Result breakdown |
| GET | `/api/audit-log` | Admin | Filtered audit trail |
| GET | `/api/audit-log/export` | Admin | CSV export |

Full OpenAPI schema to be generated from code via `apiflask`/`flask-smorest` and published at `/api/docs`.

---

## 9. UI/UX Specification — "World-Class" Design System

### 9.1 Design Principles
- **Clarity over decoration.** Every animation must communicate state (loading, success, transition) — never purely ornamental.
- **Consistency via tokens.** One spacing scale, one radius scale, one shadow scale, one motion-duration scale, enforced through Tailwind config + CSS variables.
- **Trust-forward visual language.** Because this is a security-critical civic product, use a confident, restrained palette (deep indigo/blue primary + a single accent, e.g. emerald for "success/verified" states), generous whitespace, and visible security cues (lock icons, "encrypted" badges, hash/receipt displays) — the same trust-signalling pattern used by fintech and e-gov products.
- **Motion budget.** Page-level transitions 200–400ms, micro-interactions 100–200ms, easing `cubic-bezier(0.16, 1, 0.3, 1)` ("ease-out-expo" feel) — same family of easing curves used in Apple/Linear/Stripe marketing sites. All motion respects `prefers-reduced-motion`.

### 9.2 Homepage Specification (public, no login)

A single, scroll-driven marketing/informational page, section by section:

1. **Navbar** — logo/wordmark, sticky on scroll with blur/glass background, links to sections, "Voter Login" and "Admin Login" buttons, mobile hamburger with slide-in menu (Alpine.js).
2. **Hero** — full-viewport section: headline ("A Secure, Verifiable Way to Choose Your Student Leaders"), subheadline, primary CTA ("Cast Your Vote") + secondary CTA ("How It Works"), animated background (subtle particle/gradient mesh or GSAP-animated abstract ballot/shield motif), scroll-cue indicator.
3. **Problem → Solution** — two-column narrative pulled from Chapter 1 (manual ballot risks vs. cryptographic solution), animated counter stats (e.g., "83% of surveyed institutions still use manual ballots — Ogunleye & Yusuf, 2021") revealing on scroll.
4. **How It Works** — 4-step horizontal/vertical timeline (Register → Authenticate → Vote (encrypted) → Verify receipt), icon-led (Lucide), scroll-triggered reveal.
5. **Security Architecture** — visual cards for each control: RSA-2048 Encryption, SHA-256 Integrity, Bcrypt Passwords, Role-Based Access Control, Audit Trail, HTTPS/TLS — each with a short plain-language explanation and a technical tooltip.
6. **System Features Grid** — bento-grid style cards (a layout pattern popularised by Apple/large product marketing sites): Real-time turnout, Instant results, Tamper-evident ballots, Vote receipts, Admin console, Audit exports.
7. **Live/Published Results Preview** — Chart.js donut/bar preview linking to the full public results page (only populated once an election is published; otherwise shows an elegant "No results published yet" state).
8. **Project Team Section** — required section:
   - **Supervisor card:** photo, name ("Dr. Ogunbanwo"), title ("Project Supervisor"), department.
   - **Student Researcher card:** photo, name ("Alabi Kayode Emmanuel"), matric number ("20220204224"), programme ("B.Sc. Computer Science").
   - Presented as matched, elegant profile cards (image, gradient border/hover-lift on hover, subtle tilt/scale micro-interaction).
9. **Institution Banner** — TASFUED name/crest, department, college, submission context.
10. **FAQ** — accordion (Alpine.js `x-collapse`) covering ballot secrecy, one-vote enforcement, what happens if I lose connection mid-vote, etc.
11. **Footer** — sitemap links, security/privacy note, contact, GitHub/report links, year.

### 9.3 Application Screens (post-login)
- **Voter dashboard** — election status card (countdown to open/close), "Vote Now" CTA (disabled + reason if not eligible/already voted), past receipts list.
- **Ballot casting screen** — one position per step (stepper pattern) or single-scroll form with sticky "Review" summary bar; explicit review-then-confirm modal before submission; success screen with receipt + downloadable PDF + subtle confetti/checkmark animation (respecting reduced-motion).
- **Admin console** — sidebar layout (elections, candidates, voters, audit log, settings), data tables with sort/filter, election lifecycle stepper control, live turnout chart, danger-zone confirmation modals for irreversible actions (tally, publish).
- **Results Viewer screen** — public, read-only, Chart.js breakdown per position, export button.
- **Auth screens** — centered card, split-screen on desktop (branding illustration left, form right), inline validation, password-strength meter.

### 9.4 Component/Icon/Animation Inventory
- Icons: Lucide (`lock`, `shield-check`, `fingerprint`, `check-circle-2`, `bar-chart-3`, `users`, `file-text`, `clock`, `download`).
- Motion: GSAP + ScrollTrigger for homepage; Motion One (or plain CSS transitions) for app screens to keep bundle light where it matters most (post-login flows).
- Charts: Chart.js (`doughnut` for vote share, `bar` for turnout by position).
- Fonts: `Inter` (400/500/600/700) for UI text, `Sora` (600/700) for display headings — both via Google Fonts CDN with `font-display: swap`.

---

## 10. Project Structure

```
evoting-system/
├── app/
│   ├── __init__.py            # app factory
│   ├── config.py
│   ├── extensions.py          # db, login_manager, csrf, bcrypt
│   ├── models/                # SQLAlchemy models
│   ├── services/              # AuthService, BallotService, CryptoService, TallyService, AuditService
│   ├── repositories/          # data-access layer
│   ├── routes/                # blueprints: public, auth, voter, admin, api, results
│   ├── templates/
│   │   ├── partials/          # navbar, footer, toasts
│   │   ├── components/        # Jinja macros: card.html, button.html, badge.html
│   │   ├── homepage/
│   │   ├── auth/
│   │   ├── voter/
│   │   └── admin/
│   ├── static/
│   │   ├── css/ (tailwind input/output)
│   │   ├── js/ (alpine components, gsap init, chart configs)
│   │   └── img/ (team photos, icons, illustrations)
│   └── utils/
├── migrations/                # Alembic
├── tests/
│   ├── unit/
│   └── integration/
├── keys/                      # generated PEMs (gitignored)
├── scripts/                   # seed data, key generation CLI
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── tailwind.config.js
├── .env.example
└── README.md
```

---

## 11. Testing & Quality Strategy

| Layer | Approach |
|---|---|
| Unit tests | `CryptoService` (encrypt/decrypt round-trip, hash verify/tamper-detect), `AuthService` (bcrypt, RBAC guard logic), `BallotService` (one-vote enforcement, idempotency) |
| Integration tests | Full request/response cycles per role (Pytest + Flask test client) |
| Security tests | Reproduce the paper's five test classes: authentication, replay attack, SQL injection, ballot integrity, session security — automated where possible, OWASP ZAP scan in CI |
| Load tests | Locust/k6 script simulating ≥ 200 concurrent voters at ballot submission |
| Accessibility | axe-core automated pass + manual keyboard-nav pass on Homepage and ballot flow |
| Visual/UX QA | Lighthouse CI budget: Performance ≥ 90, Accessibility ≥ 95, Best Practices ≥ 90 |
| Acceptance criteria | Every `FR-xxx` in §2 has a corresponding automated or documented manual test before sign-off |

---

## 12. Delivery Plan (Phases)

| Phase | Scope |
|---|---|
| 0. Foundation | Repo scaffold, CI, design tokens, DB models + migrations, auth skeleton |
| 1. Homepage | Full public marketing/info homepage per §9.2, fully responsive + animated |
| 2. Auth & Voter Roster | Registration (roster-gated), login, password reset, RBAC guards |
| 3. Election & Candidate Management | Admin CRUD, lifecycle state machine, CSV import |
| 4. Cryptographic Ballot Flow | Key generation, encryption service, ballot casting UI, receipts |
| 5. Tally & Results | Decryption/verification pipeline, results publishing, public results page |
| 6. Audit Trail & Admin Analytics | Audit log UI, turnout charts, CSV/PDF export |
| 7. Hardening & QA | Security test suite, load test, accessibility pass, Lighthouse budget |
| 8. Deployment | Dockerize, CI/CD pipeline, staging → production cutover, TLS |

---

## 13. Acceptance Criteria Summary

The implementation is considered complete when:
1. All `FR-xxx` requirements in §2 are implemented and covered by a passing automated test or documented manual verification.
2. All `NFR-xxx` requirements in §3 are measured and met (Lighthouse scores, load test report, coverage report attached).
3. The Homepage includes the Supervisor and Student Researcher profile section exactly as specified in §9.2.9.
4. A full election lifecycle (create → register voters → open → vote → close → tally → publish) can be demonstrated end-to-end without manual DB intervention.
5. Security test results reproduce or exceed the paper's Chapter 4 findings (resistance to replay, SQL injection, session hijacking; 100% integrity-hash verification accuracy).

---

*This specification is derived from and remains consistent with the approved TASFUED research paper "Design and Implementation of a Secure Electronic Voting System Using Cryptographic Techniques for Student Union Elections" (Alabi Kayode Emmanuel, Supervisor: Dr. Ogunbanwo, May 2026).*