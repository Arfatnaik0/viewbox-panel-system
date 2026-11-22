# ViewBox Panel System

## 1. Project overview

ViewBox helps Concave Insights manage its paid survey panel. Members sign in by phone and complete their profiles. Staff can create signup links and identify which source brought in each new member. Personal referral links credit the member who shared them.

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

Open [ViewBox](http://localhost:5173). Vite forwards `/api` requests to the backend on port 8000. The seed command can be rerun to restore any missing demo records.

Run the API integration tests from the repository root with the backend virtual environment active:

```sh
python -m pip install -r backend/requirements-dev.txt
PYTHONPATH=backend python -m pytest -q tests
```

## 4. Demo logins and test data

| Try | Details |
| --- | --- |
| Returning member | Enter `+91 98765 43210` and use the demo OTP displayed on screen. |
| New member through a source | Open the [Mumbai WhatsApp link](http://localhost:5173/join/mumbai-whatsapp) or the [Instagram link](http://localhost:5173/join/instagram) and enter a fresh demo number such as `+91 98765 43211`. |
| New member through a referral | Open the [demo member's personal link](http://localhost:5173/join/demo-member) and use a fresh demo number. |
| Admin | Open [staff sign-in](http://localhost:5173/admin/login) and use `admin@viewbox.test` / `ViewBoxDemo!32`. Create a source, copy its link, and open it in a separate browser session. |

## 5. Features

| Feature | Status |
| --- | --- |
| Source tracking, admin source setup, and signup fallback | Done |
| Member phone sign-in, profile, and personal referral link | Done |
| Live surveys, applications, eligibility, quota, and cool-off | Not done |
| Referral progress and staff review | Partly done. Signup creates the referral or records a named claim. |
| Admin respondent search, filters, export, and source reporting | Not done |
| CSV import and mock Meta lead intake | Not done |
| Fraud review, payouts, and import preview | Not done |

## 6. Database design

The [Day 2 database diagram](design/database-diagram.md) describes the full planned model. The initial migration creates the member, source, signup link, referral, staff, and sign-in tables used by the current app. See the [user flow](design/user-flow.md) and [frontend stack update](design/frontend-stack-update.md) for the planned screens and JavaScript choice.

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

## 8. Assumptions and decisions

- Source and referral credit are separate. A new member can come from Instagram and separately name a friend who referred them. A personal referral link identifies its owner automatically. A typed name is recorded for staff review.
- The link the member uses at signup gets the acquisition credit. New members without a valid tagged link choose how they heard about ViewBox. Returning members keep their original source and are matched by their normalized phone number.
- The local demo displays the OTP in the browser. Use demo contact details while testing.

## 9. Known issues and next steps

The current milestone covers onboarding and source links. Surveys, referral milestones, staff reporting, CSV import, and Meta lead intake come next. Payout handling and its gateway plan will be documented with the final submission.
