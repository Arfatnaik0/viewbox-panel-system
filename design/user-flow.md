# ViewBox Panel System: user flow

Day 2 design baseline. Later design changes belong in new files so this submission remains intact.

The prototype uses FastAPI, SQLAlchemy and SQLite for the backend, and React, Vite, TypeScript and React Router for the mobile-first frontend. The local Vite proxy forwards API requests to FastAPI.

## 1. Member entry, attribution and profile

```mermaid
flowchart TD
    subgraph Entry[Entry and source capture]
        A[Open city, staff, social, website or personal referral link] --> B[Keep latest valid source tag until signup]
        U[Open untagged signup page] --> C[Ask: How did you hear about us?]
        B --> D[Enter phone number]
        C --> D
    end
    subgraph Login[Phone login]
        D --> E[Normalize phone and request mocked OTP]
        E --> F[Enter OTP shown in demo]
        F --> G{OTP valid?}
        G -->|No| H[Show error; retry or request new OTP]
        H --> F
        G -->|Yes| I{Member already exists?}
        I -->|Yes, including imported or Meta member| J[Open existing account; preserve original attribution]
        I -->|No| K[Create member with signup source]
    end
    subgraph Referral[Referral credit at signup]
        K --> L{Verified personal referral link?}
        L -->|Yes| M[Record referring member and Lead stage]
        L -->|No| N{Referrer name entered?}
        N -->|Yes| O[Save claim for staff review; keep acquisition source]
        N -->|No| P[Continue without referral]
    end
    subgraph Profile[First login and missing profile fields]
        J --> Q{Required profile complete?}
        M --> Q
        O --> Q
        P --> Q
        Q -->|No| R[Fill missing name, date of birth, gender, city, income and interests]
        R --> S{Profile valid?}
        S -->|No| R
        S -->|Yes| T[Save profile]
        T --> V[Member home]
        Q -->|Yes| V
    end
```

Acquisition source and referring member are separate records. The last valid tagged link present at signup determines a new member's acquisition source; an untagged signup requires the fallback answer. A verified referral link credits its owner automatically. A typed referrer name becomes a staff review claim and never replaces the acquisition source. Staff can resolve the claim to a member or reject it with a reason.

The source captured for an existing member is preserved when they log in later, including members created through CSV import or Meta Ads. Matching uses the normalized phone number. Existing members only complete missing profile fields.

## 2. Live surveys, eligibility and application

```mermaid
flowchart TD
    subgraph Browse[Member home and survey details]
        A[Member home] --> B[Load live surveys; highlight interest matches]
        B --> C{Any live surveys?}
        C -->|No| D[Show no live surveys empty state]
        C -->|Yes| E[Show survey cards with eligibility and plain-language reason]
        E --> F[Open survey details]
        F --> Existing{Participation already exists?}
        Existing -->|Yes| W[My survey status]
        Existing -->|No| G[Evaluate current profile and survey rules]
    end
    subgraph Evaluate[Eligibility precedence]
        G --> H{Strict rule, quota, deadline or cool-off blocks entry?}
        H -->|Yes| I[Rejected; explain each blocking reason]
        I --> J[If cooling off, show next eligible date]
        H -->|No| K{Any flexible rule fails?}
        K -->|Yes| L[Waitlisted; explain flexible mismatch]
        K -->|No| M[Approved; show eligible to apply]
    end
    subgraph Apply[Application and member status]
        M --> N[Member applies]
        L --> O[Member joins waitlist]
        N --> P[Recheck rules and quota in one transaction]
        O --> P
        P --> Q{Participation already exists?}
        Q -->|Yes| R[Return existing participation and current status]
        Q -->|No| S{Current result?}
        S -->|Approved| T[Create approved participation and reserve one quota spot]
        S -->|Waitlisted| U[Create waitlisted participation; reserve no spot]
        S -->|Rejected| V[Show updated blocking reason; reserve no spot]
        R --> W
        T --> W
        U --> W
        V --> F
        W --> X[Show status and reason; reflect staff updates]
    end
```

An eligibility preview does not reserve capacity. Only an eligible application reserves a quota spot. A member has at most one participation per survey; repeated submissions return the existing participation. The server rechecks eligibility and capacity when the application is submitted so a stale screen cannot exceed the quota.

Strict failures, a full quota, a reached deadline and the three-month cool-off block approval. A flexible mismatch produces Waitlisted only when there is no blocking condition. Interest matches highlight surveys but do not bypass eligibility rules. The cool-off ends three calendar months after a completed survey, and the member sees the exact date.

## 3. Staff milestones and member referral visibility

```mermaid
flowchart TD
    subgraph Ops[Staff respondent and participation screen]
        A[Open respondent or survey participation] --> B[Inspect profile, eligibility, application and referral claim]
        B --> C[Review any pending named-referrer claim]
        C --> D[Accept linked member or reject claim with reason]
        B --> E{Approved participation meets survey fit?}
        E -->|Yes| F[Staff marks Fit for the survey]
        E -->|No| G[Staff records referral failure reason]
        F --> H{Full survey complete and quality check passed?}
        H -->|Yes| I[Staff marks Completed with completion time]
        H -->|No, still in progress| J[Keep Fit and show current stage]
        J --> H
        H -->|Failed or incomplete| G
        I --> K[Start three-calendar-month cool-off]
    end
    subgraph Member[Referrer's My Referrals screen]
        L[Open My Referrals] --> Share[Copy personal referral link]
        L --> M[Show referred friends with masked phone numbers]
        M --> N[Show Lead, Fit, Completed or failed with reason]
        F --> N
        G --> N
        I --> N
        D --> N
        M --> O[If no referrals, show a sharing prompt]
    end
```

Lead means the referred member signed up. Staff marks Fit on an approved survey participation and marks Completed only after full participation and a successful quality check. The same actions update source reporting and the referral linked to that participation; each referral has at most one attributable participation. A failed referral exposes its plain-language reason to the referrer. Referred phone numbers are masked, for example `98XXXXXX21`. Referral success requires the Completed milestone.

## 4. Admin sources, surveys, respondent grid and export

```mermaid
flowchart TD
    A[Admin login] --> B[Admin home]
    subgraph Sources[Source management and dashboard]
        B --> C[Sources screen]
        C --> D[Create source record and unique signup link]
        D --> E[Copy link for city group, staff, social post or website]
        C --> F[Source dashboard]
        F --> G[Show distinct signups, Fit and Completed counts]
    end
    subgraph Surveys[Survey management]
        B --> H[Create survey]
        H --> I[Enter title, dates, quota, interests and profile rules]
        I --> J[Mark each profile rule Strict or Flexible]
        J --> K{Valid rules and cycle at most 15 days?}
        K -->|No| L[Show field errors and preserve form input]
        L --> I
        K -->|Yes| M[Save and launch survey]
        M --> N[Survey appears in member live list during its window]
    end
    subgraph Respondents[Respondent grid]
        B --> O[Open respondent grid]
        O --> P[Search as typed by name, member ID or city]
        P --> Q[Filter by source, city and status]
        Q --> R[Show matching rows and result count]
        R --> S[Open respondent details and participation history]
        R --> T[Export current search and filters as CSV]
        R --> U[If no matches, show clear-filters empty state]
    end
```

Sources are editable database records, so adding a channel such as LinkedIn needs no code change. Every member also receives a personal referral link. Source/program stage counts use distinct members to avoid inflating results through repeated requests or multiple records. The exported dataset uses the same search and filter conditions as the visible grid.

Admin pages require the admin role. Staff actions require staff or admin access. Respondents can view only their own profile, applications and referral information.

## 5. Existing-member CSV import

```mermaid
flowchart TD
    A[Admin opens import screen] --> B[Upload viewbox_respondents_sample.csv]
    B --> C{Readable CSV and recognized columns?}
    C -->|No| D[Show file error; allow another upload]
    C -->|Yes| E[Read rows; normalize phones and repair safe formatting errors]
    E --> F{Row valid?}
    F -->|No| G[Skip row and record row number and reason]
    F -->|Yes| H{Normalized phone already exists?}
    H -->|Yes| I[Match existing member; preserve attribution]
    H -->|No| J[Create imported member]
    I --> Map[Record unambiguous legacy ID mapping]
    J --> Map
    Map --> K[Continue processing other rows]
    G --> K
    K --> L[Second pass: resolve referral references using legacy ID mapping]
    L --> M[Report unresolved references for staff review]
    M --> N[Show imported, matched, repaired and skipped totals with row reasons]
    N --> O[Imported members available in respondent grid]
```

Bad rows do not crash or abort the whole import. The result reports what was repaired or skipped and why. Legacy referral IDs are resolved after valid member rows have been processed, so a referral can point to a member appearing later in the file. Imported members subsequently access the same account through normalized-phone OTP login.

## 6. Mock Meta lead intake

```mermaid
flowchart TD
    A[Send documented mock Meta lead request] --> B[Validate lead ID, campaign and required form fields]
    B --> C{Valid payload?}
    C -->|No| D[Return field errors; create no member]
    C -->|Yes| E{Lead ID already processed?}
    E -->|Yes| F[Return existing processing result; create no duplicate]
    E -->|No| G[Normalize lead phone]
    G --> H{Member with this phone exists?}
    H -->|Yes| I[Link lead to existing member; preserve attribution]
    H -->|No| J[Create member with Meta Ads source]
    I --> K[Save unique lead ID, campaign and available Meta metadata]
    J --> K
    K --> L[Return member reference and result]
    L --> M[Member later logs in with OTP and fills missing profile fields]
```

The endpoint accepts a mock lead in the researched Meta lead format, retaining lead and campaign identifiers plus available form, ad and timestamp metadata. It validates required details and deduplicates on lead ID. A new lead with an existing phone attaches to the existing member without replacing that member's original acquisition source. The README will document the endpoint, an example request and its response so it can be exercised locally without a real ad.

## Shared screen states

- Data screens show a loading state, a useful empty state and a retryable load error.
- Forms retain entered values after validation errors and display field-specific messages.
- Application submission disables repeated taps while pending; the server enforces participation uniqueness and quota limits.
- Import and Meta errors include actionable reasons without exposing another member's private data.
