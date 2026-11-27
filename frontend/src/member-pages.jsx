import { useContext, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "./api.js";
import { SessionContext } from "./session.js";
import {
  Eligibility,
  formatDate,
  Loading,
  Notice,
  ResourceError,
  Status,
  useResource,
} from "./portal-ui.jsx";

function SurveyCard({ survey }) {
  return (
    <article className="card survey-card">
      <div className="section-heading">
        <h3>
          <Link to={`/surveys/${survey.id}`}>{survey.title}</Link>
        </h3>
        {survey.interest_match && (
          <span className="survey-interest">Matches your interests</span>
        )}
      </div>
      <p className="muted">
        {survey.description ||
          "Open this survey to review its eligibility and application status."}
      </p>
      <p className="survey-meta">Closes {formatDate(survey.closes_at, true)}</p>
      {survey.participation ? (
        <div className="action-row">
          <span className="field-help">Your application</span>
          <Status
            value={
              survey.participation.completed_at
                ? "completed"
                : survey.participation.fit_at
                  ? "fit"
                  : survey.participation.eligibility_status
            }
          />
        </div>
      ) : (
        <Eligibility eligibility={survey.eligibility} />
      )}
      <Link className="text-button" to={`/surveys/${survey.id}`}>
        View survey <span aria-hidden="true">→</span>
      </Link>
    </article>
  );
}

export function MemberSurveys({ embedded = false }) {
  const Heading = embedded ? "h2" : "h1";
  const resource = useResource("/member/surveys");
  const live = (resource.data || []).filter((survey) => survey.live);
  const past = (resource.data || []).filter(
    (survey) => !survey.live && survey.participation,
  );
  return (
    <section
      className={embedded ? "survey-section" : "workspace-page"}
      aria-labelledby="survey-list-title"
    >
      <div className="workspace-heading">
        <div>
          {!embedded && <p className="eyebrow">MEMBER SURVEYS</p>}
          <Heading
            className={embedded ? "section-title" : "page-title"}
            id="survey-list-title"
          >
            Live surveys
          </Heading>
          <p className="muted">
            Check your eligibility before you apply. Interest matches are
            highlighted.
          </p>
        </div>
        {embedded && (
          <Link className="text-button" to="/surveys">
            All surveys →
          </Link>
        )}
      </div>
      <ResourceError error={resource.error} retry={resource.reload} />
      {resource.loading ? (
        <Loading>Loading surveys…</Loading>
      ) : (
        !resource.error && (
          <>
            {live.length ? (
              <div className="survey-grid">
                {live.map((survey) => (
                  <SurveyCard key={survey.id} survey={survey} />
                ))}
              </div>
            ) : (
              <div className="card empty-inline">
                <h2>No live surveys right now</h2>
                <p className="muted">
                  Check back for new research.
                  {past.length > 0 &&
                    " Your previous applications remain available below."}
                </p>
              </div>
            )}
            {past.length > 0 && (
              <section className="past-surveys">
                <h2>Previous applications</h2>
                <p className="muted">
                  Your existing applications stay visible after a survey closes.
                </p>
                <div className="survey-grid">
                  {past.map((survey) => (
                    <SurveyCard key={survey.id} survey={survey} />
                  ))}
                </div>
              </section>
            )}
          </>
        )
      )}
    </section>
  );
}

export function SurveyDetail() {
  const { id } = useParams();
  const resource = useResource(`/member/surveys/${encodeURIComponent(id)}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  async function apply() {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const updated = await api(
        `/member/surveys/${encodeURIComponent(id)}/apply`,
        { method: "POST" },
      );
      resource.setData(updated);
      setSuccess(
        updated.participation
          ? updated.participation.eligibility_status === "waitlisted"
            ? "You are on the waitlist. No quota spot has been reserved."
            : "Your application is saved. Your current status is shown below."
          : "Your eligibility changed. Please review the updated reason below.",
      );
    } catch (err) {
      setError(err.message);
      resource.reload();
    } finally {
      setBusy(false);
    }
  }
  const survey = resource.data;
  const participation = survey?.participation;
  return (
    <div className="workspace-page">
      <Link className="back-link" to="/surveys">
        ← Back to surveys
      </Link>
      <ResourceError error={resource.error} retry={resource.reload} />
      {resource.loading ? (
        <Loading>Loading survey details…</Loading>
      ) : (
        survey && (
          <>
            <div className="workspace-heading">
              <div>
                <p className="eyebrow">SURVEY DETAILS</p>
                <h1 className="page-title">{survey.title}</h1>
                {survey.interest_match && (
                  <span className="survey-interest">
                    Matches your interests
                  </span>
                )}
              </div>
              <Status value={survey.live ? "live" : "closed"} />
            </div>
            <div className="two-column">
              <section className="card panel-stack">
                <h2>About this survey</h2>
                <p className="muted preserve-lines">
                  {survey.description ||
                    "No additional description was provided."}
                </p>
                <dl className="detail-grid">
                  <div className="detail-item">
                    <dt>Opens</dt>
                    <dd>{formatDate(survey.opens_at, true)}</dd>
                  </div>
                  <div className="detail-item">
                    <dt>Closes</dt>
                    <dd>{formatDate(survey.closes_at, true)}</dd>
                  </div>
                  <div className="detail-item">
                    <dt>Survey capacity</dt>
                    <dd>{survey.quota} participants</dd>
                  </div>
                </dl>
                <p className="field-help">
                  An eligibility check does not reserve a place. Capacity is
                  checked again when you apply.
                </p>
              </section>
              <section className="card panel-stack">
                <h2>
                  {participation ? "Your application" : "Your eligibility"}
                </h2>
                <Notice kind="error">{error}</Notice>
                <Notice kind="success">{success}</Notice>
                {participation && (
                  <div className="action-row">
                    <Status
                      value={
                        participation.completed_at
                          ? "completed"
                          : participation.fit_at
                            ? "fit"
                            : participation.eligibility_status
                      }
                    />
                    <span className="field-help">
                      Application #{participation.id}
                    </span>
                  </div>
                )}
                <Eligibility eligibility={survey.eligibility} />
                {participation ? (
                  <>
                    <p className="muted">
                      Your application is already saved. Reopening this page
                      does not create a duplicate.
                    </p>
                    {participation.fit_at && (
                      <p className="field-help">
                        Marked Fit: {formatDate(participation.fit_at, true)}
                      </p>
                    )}
                    {participation.completed_at && (
                      <p className="field-help">
                        Completed after quality check:{" "}
                        {formatDate(participation.completed_at, true)}
                      </p>
                    )}
                  </>
                ) : survey.live && survey.eligibility?.status !== "rejected" ? (
                  <button className="button" onClick={apply} disabled={busy}>
                    {busy
                      ? "Saving your application…"
                      : survey.eligibility?.status === "waitlisted"
                        ? "Join waitlist"
                        : "Apply for this survey"}
                  </button>
                ) : (
                  <p className="field-help">
                    {survey.live
                      ? "You cannot apply while a blocking eligibility condition is present."
                      : "This survey is not currently open for applications."}
                  </p>
                )}
              </section>
            </div>
          </>
        )
      )}
    </div>
  );
}

function PersonalLink() {
  const { member } = useContext(SessionContext);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);
  const url = member.referral_token
    ? `${window.location.origin}/join/${encodeURIComponent(member.referral_token)}`
    : "";
  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setError(false);
      setMessage("Your referral link was copied.");
    } catch {
      setError(true);
      setMessage(
        "Copy is unavailable here. Select and copy the link manually.",
      );
    }
  }
  return (
    <section className="card panel-stack">
      <h2>Your personal referral link</h2>
      <p className="muted">
        Friends who sign up through this link are connected to you
        automatically.
      </p>
      {url ? (
        <>
          <label className="field-label" htmlFor="my-referral-link">
            Share this signup link
          </label>
          <div className="referral-link-row">
            <input
              className="input referral-link"
              id="my-referral-link"
              value={url}
              readOnly
              onFocus={(event) => event.target.select()}
            />
            <button className="button button-secondary" onClick={copy}>
              Copy link
            </button>
          </div>
          <Notice kind={error ? "error" : "success"}>{message}</Notice>
        </>
      ) : (
        <Notice kind="warning">
          Your referral link is unavailable. Please contact the ViewBox team.
        </Notice>
      )}
    </section>
  );
}

export function MyReferrals() {
  const resource = useResource("/member/referrals");
  return (
    <div className="workspace-page">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">MEMBER REFERRALS</p>
          <h1 className="page-title">My referrals</h1>
          <p className="muted">
            Follow each friend from signup to Fit and quality-checked
            completion.
          </p>
        </div>
      </div>
      <PersonalLink />
      <section className="survey-section">
        <h2>Referral progress</h2>
        <ResourceError error={resource.error} retry={resource.reload} />
        {resource.loading ? (
          <Loading>Loading your referrals…</Loading>
        ) : (
          !resource.error &&
          (resource.data?.length ? (
            <div className="list-stack">
              {resource.data.map((referral) => (
                <article className="card referral-person" key={referral.id}>
                  <div className="section-heading">
                    <div>
                      <h3>{referral.name || "New member"}</h3>
                      <p className="muted">{referral.phone_masked}</p>
                    </div>
                    <Status value={referral.stage} />
                  </div>
                  {referral.failure_reason && (
                    <Notice kind="warning">
                      Reason: {referral.failure_reason}
                    </Notice>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <div className="card empty-inline">
              <h3>No referrals yet</h3>
              <p className="muted">
                Share your personal link. Friends will appear here after they
                sign up.
              </p>
            </div>
          ))
        )}
      </section>
    </div>
  );
}
