# ViewBox Panel System

## 1. Project overview

ViewBox helps Concave Insights manage its paid survey panel. Members sign in by phone, check their survey eligibility, apply, and follow their referrals. Admins create signup links and surveys. Staff track survey and referral progress, export filtered respondent lists, and compare outcomes by signup source.

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

The demo also includes **Food delivery habits**. Its flexible Pune rule lets the Mumbai demo members try joining a waitlist.

## 5. Features

| Feature | Status |
| --- | --- |
| Source tracking, admin source setup, and signup fallback | Done |
| Member phone sign-in, profile, and personal referral link | Done |
| Live surveys, applications, eligibility, quota, and cool-off | Done |
| Referral progress and staff review | Done |
| Respondent search, filters, CSV export, and source reporting | Done |
| CSV import and mock Meta lead intake | Not done |
| Fraud review, payouts, and import preview | Not done |

## 6. Database design

The [Day 2 database diagram](design/database-diagram.md) describes the full planned model. The current migrations cover member accounts, signup sources, staff accounts, surveys, rules, interests, applications, and referrals. An approved application counts toward the survey quota. A verified referral follows a single qualifying application from Fit to Completed. See the [user flow](design/user-flow.md) and [frontend stack update](design/frontend-stack-update.md).

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

## 8. Assumptions and decisions

- Source and referral credit are separate. A new member can come from Instagram and separately name a friend who referred them. A personal referral link identifies its owner automatically. A typed name is recorded for staff review.
- The link the member uses at signup gets the acquisition credit. New members without a valid tagged link choose how they heard about ViewBox. Returning members keep their original source and are matched by their normalized phone number.
- The local demo displays the OTP in the browser. Use demo contact details while testing.
- Eligibility previews leave survey capacity available. Applications reserve a spot only when approved. A flexible rule mismatch puts the member on the waitlist when every strict rule and operating limit is met.
- A completed survey starts a cool-off of three calendar months. Staff record Fit and Completed separately. Source totals count each member once per milestone, even when that member has several applications.

## 9. Known issues and next steps

CSV import and mock Meta lead intake are the remaining core features. The optional fraud queue, payout ledger, and import preview follow the core work. The final submission will include the payment gateway plan and a walkthrough video.
