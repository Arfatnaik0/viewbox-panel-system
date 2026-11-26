# ViewBox Panel System

## 1. Project overview

ViewBox helps Concave Insights manage its paid survey panel. Members sign in by phone, apply to surveys, and follow their referrals. Admins create signup links and surveys. Staff manage participants, compare source outcomes, and import or export respondent data. A mock endpoint accepts Meta Ads leads.

## 2. Tech stack

- Backend: Python, FastAPI, SQLAlchemy, Alembic, and SQLite.
- Frontend: React, JavaScript and JSX, React Router, and Vite.

## 3. Setup and run

Install Python 3.12 or later and Node.js 22.12 or later. From the repository root, start the backend in one terminal:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

Start the frontend in another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open [ViewBox](http://localhost:5173). Vite forwards `/api` requests to the backend on port 8000. For an existing database, run `alembic upgrade head` before rerunning the demo seed.

Run the API integration tests from the repository root with the backend virtual environment active:

```sh
python -m pip install -r backend/requirements-dev.txt
PYTHONPATH=backend python -m pytest -q tests
```

## 4. Demo logins and test data

| Try | Details |
| --- | --- |
| Returning member | Enter `+91 98765 43210` and use the demo OTP displayed on screen. |
| Referred demo member | Enter `+91 98765 43299`. Apply to **Everyday shopping in Mumbai**, then use a separate staff session to mark the application Fit and Completed. The first demo member can follow the progress under **My referrals**. |
| New member through a source | Open the [Mumbai WhatsApp link](http://localhost:5173/join/mumbai-whatsapp) or the [Instagram link](http://localhost:5173/join/instagram) and enter a fresh demo number such as `+91 98765 43211`. |
| New member through a referral | Open the [demo member's personal link](http://localhost:5173/join/demo-member) and use a fresh demo number. |
| Admin | Open [staff sign-in](http://localhost:5173/admin/login) and use `admin@viewbox.test` / `ViewBoxDemo!32` to manage surveys and signup links. |
| Operations staff | Use `staff@viewbox.test` / `ViewBoxStaff!32` at the same sign-in. Search for **Referred Demo Member** to manage their applications or see their referral. |

The demo also includes **Food delivery habits**. Its flexible Pune rule lets the Mumbai demo members try joining a waitlist. In **CSV import**, use [the synthetic respondent sample](examples/demo-respondents.csv) to preview two valid rows and one rejected row. The supplied assessment CSV can be uploaded separately. The [mock Meta payload](examples/meta-lead.json) is also synthetic.

## 5. Features

| Feature | Status |
| --- | --- |
| Source tracking, admin source setup, and signup fallback | Done |
| Member phone sign-in, profile, and personal referral link | Done |
| Live surveys, applications, eligibility, quota, and cool-off | Done |
| Referral progress and staff review | Done |
| Respondent search, filters, CSV export, and source reporting | Done |
| Messy CSV import, preview, and row-level report | Done |
| Mock Meta lead intake and duplicate protection | Done |
| Fraud review queue and payout ledger | Not done |

## 6. Database design

The [Day 2 database diagram](design/database-diagram.md) describes the panel model. React sends same-origin requests through Vite's local proxy. FastAPI validates requests and permissions. SQLAlchemy records changes in SQLite, and Alembic applies schema changes. A normalized phone identifies one member. Sources and personal referral credit are separate, and a referral follows one qualifying application. Legacy keys link CSV referral rows on a second pass, while unique Meta lead IDs prevent repeat deliveries from creating another lead. See the [user flow](design/user-flow.md) and [frontend stack update](design/frontend-stack-update.md).

## 7. API endpoints

FastAPI provides [interactive API documentation](http://localhost:8000/docs) when the backend is running. Member and admin authentication both use HTTP-only cookies.

| Method and path | Purpose | Example request → response |
| --- | --- | --- |
| `GET /api/health` | Check the API is up | No body → `{"status":"ok"}` |
| `GET /api/signup/sources` | List available signup sources | No body → `[{"id":1,"name":"Mumbai WhatsApp"}]` |
| `GET /api/signup/links/{token}` | Validate a tracked signup link | `mumbai-whatsapp` → `{"source":{"id":1,"name":"Mumbai WhatsApp"},"personal":false}` |
| `POST /api/auth/otp/request` | Request a demo OTP | `{"phone":"+919876543210"}` → `{"challenge_id":"…","demo_code":"123456"}` |
| `POST /api/auth/otp/verify` | Verify a code and sign in | `{"challenge_id":"…","code":"123456","source_token":"mumbai-whatsapp"}` → member and session cookie |
| `GET /api/member/me` | Read the current member | Session cookie → member, including `source`, `profile_complete`, and `referral_token` |
| `PUT /api/member/profile` | Save the current member's profile | `{"name":"Dev Patel","date_of_birth":"1996-06-12","gender":"male","city":"Mumbai","income_range":"50000_100000","interests":["Travel"]}` → updated member |
| `POST /api/auth/logout` | End the current session | Session cookie → `204 No Content` |
| `POST /api/admin/login` | Sign in as an admin | `{"email":"admin@viewbox.test","password":"ViewBoxDemo!32"}` → admin email and session cookie |
| `GET /api/admin/me` | Read the current admin | Admin session cookie → `{"email":"admin@viewbox.test"}` |
| `GET /api/admin/sources` | List sources and their shareable tokens | Admin session cookie → `[{"id":1,"name":"Mumbai WhatsApp","token":"mumbai-whatsapp"}]` |
| `POST /api/admin/sources` | Add a source and create its signup link | `{"name":"LinkedIn"}` → source ID, name, and link token |
| `GET /api/admin/session` | Read the staff account and role | Staff session cookie → `{"email":"staff@viewbox.test","role":"staff"}` |
| `GET /api/admin/surveys` | List surveys for admins | Admin session cookie → survey records |
| `POST /api/admin/surveys` | Create a draft or published survey | `{"title":"Shopping","description":"Tell us how you shop.","opens_at":"2026-11-25T10:00:00Z","closes_at":"2026-12-02T10:00:00Z","quota":20,"published":false,"interests":["Shopping"],"rules":[{"field":"age","mode":"strict","values":[18,65]}]}` → `201` survey record |
| `PATCH /api/admin/surveys/{id}/publish` | Publish or hide a survey | `{"published":true}` → updated survey |
| `GET /api/member/surveys` | List live surveys and the member's existing applications | Member session cookie → survey summaries with interest match and eligibility |
| `GET /api/member/surveys/{id}` | Preview a survey and its eligibility decision | Survey ID → survey with `eligibility` and `participation` |
| `POST /api/member/surveys/{id}/apply` | Apply or join the waitlist | Survey ID, no body → current decision and any saved application |
| `GET /api/member/referrals` | Read personal referral progress | Member session cookie → referrals with masked phone numbers and any failure reason |
| `GET /api/admin/respondents` | Find and filter respondents | `?search=Mumbai&status=active` → `{"respondents":[…],"filters":{"sources":[…],"cities":[…],"statuses":[…]}}` |
| `GET /api/admin/respondents/export` | Download the filtered list | Same query as the grid → CSV download |
| `GET /api/admin/respondents/{id}` | Read respondent, referral, and application details | Respondent ID → record with `participations` |
| `POST /api/admin/participations/{id}/fit` | Mark an approved application Fit | Application ID, no body → `204 No Content` |
| `POST /api/admin/participations/{id}/complete` | Confirm participation and a passed quality check | Application ID, no body → `204 No Content` |
| `POST /api/admin/referrals/{id}/review` | Resolve a named referral claim | `{"referrer_member_id":1}` or `{"failure_reason":"Referrer could not be verified."}` → `204 No Content` |
| `POST /api/admin/referrals/{id}/fail` | Record why a verified referral failed | `{"reason":"Survey participation was incomplete."}` → `204 No Content` |
| `GET /api/admin/source-stats` | Compare signup and survey milestones by source | Staff session cookie → `[{"id":1,"name":"Mumbai WhatsApp","signups":1,"fit":0,"completed":0}]` |
| `POST /api/admin/imports/respondents?preview=true` | Preview a respondent CSV (use `preview=false` to save) | Multipart field `file` → `{"preview":true,"summary":{"total":3,"created":2,"matched":0,"fixed":2,"skipped":1},"issues":[{"row":4,"action":"skipped","reason":"Invalid phone number."}]}` (abridged example) |
| `POST /api/integrations/meta/leads` | Accept an enriched mock Meta lead | [Example lead payload](examples/meta-lead.json) → `201 {"lead_id":"demo-lead-001","member_id":3,"campaign_id":"demo-campaign-001","created_member":true,"duplicate":false}`. Repeating the lead ID returns `200` with `duplicate:true`. |

### Try the mock Meta endpoint

In a live integration, Meta sends a Page `leadgen` webhook with a lead ID. The receiver uses that ID to fetch the submitted fields and campaign data from the Graph API. This local endpoint accepts the enriched record directly. It requires a demo admin session and makes no requests to Meta. [Meta lead webhooks](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/webhooks-for-leadgen/) · [Meta lead retrieval](https://developers.facebook.com/docs/marketing-api/guides/lead-ads/retrieving/)

Run from the repository root while the backend is running:

```sh
cookie_jar=$(mktemp)
curl --fail-with-body -sS -c "$cookie_jar" 'http://localhost:8000/api/admin/login' \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@viewbox.test","password":"ViewBoxDemo!32"}'
curl --fail-with-body -sS -b "$cookie_jar" 'http://localhost:8000/api/integrations/meta/leads' \
  -H 'Content-Type: application/json' --data-binary @examples/meta-lead.json
rm -f "$cookie_jar"
```

An invalid payload returns `422` with a validation error. A new lead from an existing phone is linked to that member and preserves their original acquisition source.

## 8. Assumptions and decisions

- Source and referral credit are separate. A new member can come from Instagram and separately name a friend who referred them. A personal referral link identifies its owner automatically. A typed name is recorded for staff review.
- The link the member uses at signup gets the acquisition credit. New members without a valid tagged link choose how they heard about ViewBox. Returning members keep their original source and are matched by their normalized phone number.
- The local demo displays the OTP in the browser. Use demo contact details while testing.
- Eligibility previews leave survey capacity available. Applications reserve a spot only when approved. A flexible rule mismatch puts the member on the waitlist when every strict rule and operating limit is met.
- A completed survey starts a cool-off of three calendar months. Staff record Fit and Completed separately. Source totals count each member once per milestone, even when that member has several applications.
- The CSV import normalizes known formats and source aliases, preserves annual income bands, and reports uncertain or unusable values. A preview writes nothing. Existing phones retain their original attribution. Legacy referral IDs are used only when the match is unambiguous.

### Payment gateway plan

RazorpayX fits the planned INR payouts to verified Indian bank accounts. After staff approve a ledger entry for a completed survey or referral, a worker would create or reuse the payee Contact (`POST /v1/contacts`) and Fund Account (`POST /v1/fund_accounts`), then send `POST /v1/payouts` with the amount in paise and a stable `X-Payout-Idempotency` key. Store the provider payout ID and reconcile it with signed webhooks and `GET /v1/payouts/{id}`. [RazorpayX payout APIs](https://razorpay.com/docs/api/x/payouts/) · [RazorpayX webhook states](https://axisbank-docs.razorpay.com/razorpayx/webhooks/payloads/)

Keep queued or processing transfers pending. On a timeout, check the existing transfer or retry the same request with the same key. Mark a ledger entry paid only after a confirmed processed state. Route failures and reversals to staff for review before authorizing any new transfer.

## 9. Known issues and next steps

This is a local prototype. Phone verification shows a demo OTP, lead intake uses a mock payload, and survey completion is confirmed by operations staff. Real SMS, signed Meta webhooks, fraud review, and payout integration are future work. Use synthetic records in public demonstrations.
