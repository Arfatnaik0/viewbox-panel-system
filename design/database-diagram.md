# Database diagram

ViewBox uses SQLite with SQLAlchemy. Each respondent has one member record. Acquisition, referrals, eligibility, and survey outcomes are tracked separately so staff can report on them without counting a person twice.

```mermaid
erDiagram
    SOURCE ||..o{ SIGNUP_LINK : provides
    SOURCE ||..o{ MEMBER : acquires
    MEMBER o|..o| SIGNUP_LINK : owns
    SIGNUP_LINK o|..o{ MEMBER : tags
    MEMBER ||..o{ META_LEAD : receives
    MEMBER ||..o{ LEGACY_MEMBER_KEY : maps
    MEMBER ||..o| REFERRAL : is_referred_in
    MEMBER o|..o{ REFERRAL : refers
    PARTICIPATION o|..o| REFERRAL : qualifies
    MEMBER ||..o{ PARTICIPATION : applies
    SURVEY ||..o{ PARTICIPATION : receives
    STAFF_ACCOUNT o|..o{ PARTICIPATION : marks_fit
    STAFF_ACCOUNT o|..o{ PARTICIPATION : confirms_completion
    SURVEY ||..o{ SURVEY_RULE : defines
    MEMBER ||--o{ MEMBER_INTEREST : selects
    INTEREST ||--o{ MEMBER_INTEREST : classifies
    SURVEY ||--o{ SURVEY_INTEREST : targets
    INTEREST ||--o{ SURVEY_INTEREST : classifies

    SOURCE {
        integer id PK
        string name UK
        boolean active
    }
    SIGNUP_LINK {
        integer id PK
        integer source_id FK
        integer owner_member_id FK,UK "Null for admin-created links"
        string token UK
        boolean active
    }
    MEMBER {
        integer id PK
        string phone_e164 UK
        string name
        string email
        date date_of_birth
        string gender
        string city
        string income_range
        string status
        integer source_id FK
        integer signup_link_id FK "Null for untagged or imported signups"
        datetime joined_at
        datetime profile_completed_at
        date imported_last_completed_on
    }
    REFERRAL {
        integer id PK
        integer referred_member_id FK,UK
        integer referrer_member_id FK "Null while a name claim is unresolved"
        string claimed_name
        string verification_status
        string stage "Lead, Fit, Completed or Failed"
        integer participation_id FK,UK "Set when staff mark Fit for a survey"
        string failure_reason
    }
    SURVEY {
        integer id PK
        string title
        string description
        integer quota
        datetime opens_at
        datetime closes_at
        boolean published
    }
    SURVEY_RULE {
        integer id PK
        integer survey_id FK
        string field "Age, city, gender or income range"
        json allowed_values
        string mode "Strict or Flexible"
    }
    STAFF_ACCOUNT {
        integer id PK
        string email UK
        string password_hash
        string role "Staff or Admin"
    }
    PARTICIPATION {
        integer id PK
        integer member_id FK
        integer survey_id FK
        string eligibility_status "Approved or Waitlisted"
        string eligibility_reason
        datetime applied_at
        datetime fit_at
        integer fit_by_id FK
        datetime completed_at
        integer completed_by_id FK
    }
    INTEREST {
        integer id PK
        string name UK
    }
    MEMBER_INTEREST {
        integer member_id PK,FK
        integer interest_id PK,FK
    }
    SURVEY_INTEREST {
        integer survey_id PK,FK
        integer interest_id PK,FK
    }
    META_LEAD {
        string lead_id PK
        integer member_id FK
        string campaign_id
        string form_id
        string ad_id
        datetime submitted_at
    }
    LEGACY_MEMBER_KEY {
        string legacy_id PK
        integer member_id FK
    }
```

- **Signup and attribution.** Admins create named sources and unique link tokens in the database. Each source has one active admin link. A new member gets the source from the last tagged link used to reach signup, or selects an answer when no tag is present. A personal link also identifies the referring member. A name claim goes to staff for verification and does not modify the acquisition source. A member signs in by verifying their phone and completes missing profile details after login.
- **Surveys and quota.** `PARTICIPATION` is unique on `(member_id, survey_id)`. The detail page previews eligibility. Applying checks the rules again and reserves an approved place in the same database transaction as the quota check. Only published surveys within their dates are live. The window is at most 15 days. A strict rule failure, full quota, deadline, or active cool-off takes precedence over a flexible rule failure. Calculate the next eligible date as three calendar months after the latest completed participation or imported completion date, whichever is later. A shared interest highlights a survey without changing eligibility.
- **Fit and completion.** Staff record Fit on an approved participation and completion after the quality check. A verified referral starts at Lead. Once it reaches Fit, its linked participation must belong to the referred member. Only that participation can advance it to Completed. Failed referrals carry a reason. Member views show masked phone numbers. The source dashboard counts distinct members by original source, using recorded Fit and Completed milestones across their participations.
- **CSV and Meta leads.** Normalize phones before matching members. CSV rows with unusable phones are skipped, and the import reports fixed or skipped rows. Resolve `referred_by` values through unambiguous legacy IDs in a second pass. Use a Legacy Import source for missing CSV attribution and keep imported completion dates without creating survey participations. Meta validates a lead before saving it and stores campaign metadata against its unique lead ID. A retry returns the original result. New members get the Meta Ads source, while leads for existing phones preserve the member's original source.
