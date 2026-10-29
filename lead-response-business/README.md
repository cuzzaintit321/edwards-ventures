# Edwards Ventures — Small Business Lead Response System

A runnable, self-hosted lead-intake and **human-reviewed response-drafting** pilot for small service businesses.

**Pilot offer:** $300 one-time setup + $75 for the first 30 days of basic support (illustrative proposed pricing; not an integrated checkout).

## Features
- Responsive public landing page and lead intake form
- Persisted leads in SQLite (named Docker volume)
- Private dashboard: view requests, track lead status, generate and review drafts
- Explicit **template demonstration** mode, no AI provider required or implied
- No automatic outbound email or payment capture
- Docker Compose deployment on `127.0.0.1:8150`, with a health check

## Launch on yeet (Ubuntu)

```bash
cp .env.example .env
python3 - <<'PY'
from pathlib import Path
import secrets
p=Path('.env')
s=p.read_text().replace('CHANGE_TO_A_LONG_UNIQUE_PASSWORD', secrets.token_urlsafe(28)).replace('CHANGE_TO_A_RANDOM_SECRET', secrets.token_urlsafe(32))
p.write_text(s)
p.chmod(0o600)
print('Generated private credentials in .env. Read them locally to sign in.')
PY
docker compose up -d --build
docker compose ps
curl -s http://127.0.0.1:8150/health
```

On your Fedora desktop open an SSH tunnel:

```bash
ssh -o ExitOnForwardFailure=yes -N -L 8150:127.0.0.1:8150 yeet
```

Then browse `http://localhost:8150` (public form) and `http://localhost:8150/dashboard` (private lead management). Dashboard credentials are `ADMIN_USERNAME` and `ADMIN_PASSWORD` from `.env`. **Don't share, commit, or paste the secret values in chat.**

## Pilot verification
1. Submit a fake inquiry through the homepage.
2. Open `/dashboard` and authenticate.
3. Click **Generate sample reply** (deterministic template, *not real AI*) and verify the draft is saved.
4. Change the lead status and verify it persists after a restart.

## Security and scope
This is a functional **local prototype**, not a hardened multi-tenant SaaS product. Inquiries contain personal data. Keep the site bound to localhost and access it through SSH. Do **not** publish the dashboard, open port 8150 on your router, or collect real customer data until access control, HTTPS, consent/privacy, retention, backups, abuse prevention, and security review are addressed. HTTP Basic auth must only be used over a secure channel (SSH tunnel is used here). Form tokens are designed to prevent unsanctioned changes but are not a substitute for a broader security review.

Suggested commercial production extensions: real AI provider integration with explicit data-handling terms and manual approval, per-client isolation, HTTPS, email provider integration, alerts, billing, audit log, retention controls, and backup/restore procedure.

## Business files
See `docs/PILOT_OFFER.md` and `docs/LAUNCH_CHECKLIST.md`.

## GitHub
`.env`, database files, and local backups are ignored. Review `git status --short` before publishing.
