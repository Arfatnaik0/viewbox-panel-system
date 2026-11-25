import { useState } from "react";
import {
  Link,
  useLocation,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { api } from "./api.js";
import {
  Field,
  formatDate,
  Loading,
  Notice,
  ResourceError,
  Status,
  useDebounced,
  useResource,
} from "./portal-ui.jsx";

export function Respondents() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const search = params.get("search") || "";
  const delayedSearch = useDebounced(search);
  const query = new URLSearchParams();
  if (delayedSearch.trim()) query.set("search", delayedSearch.trim());
  for (const key of ["source_id", "city", "status"])
    if (params.get(key)) query.set(key, params.get(key));
  const resource = useResource(
    `/admin/respondents${query.size ? `?${query}` : ""}`,
    { keepPrevious: true },
  );
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const filters = resource.data?.filters || {
    sources: [],
    cities: [],
    statuses: [],
  };
  const rows = resource.data?.respondents || [];
  function filter(key, value) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );
  }
  async function download() {
    setExporting(true);
    setExportError("");
    try {
      const blob = await api(
        `/admin/respondents/export${query.size ? `?${query}` : ""}`,
        { responseType: "blob" },
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "viewbox-respondents.csv";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err.message);
    } finally {
      setExporting(false);
    }
  }
  return (
    <div className="workspace-page">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">OPERATIONS</p>
          <h1 className="page-title">Respondents</h1>
          <p className="muted">
            Find members, review referral claims and record survey progress.
          </p>
        </div>
        <button
          className="button button-secondary button-small"
          onClick={download}
          disabled={
            exporting ||
            resource.loading ||
            Boolean(resource.error) ||
            search !== delayedSearch
          }
        >
          {exporting ? "Preparing CSV…" : "Export filtered CSV"}
        </button>
      </div>
      <section className="card">
        <div className="filters-grid">
          <Field id="respondent-search" label="Search respondents">
            <input
              className="input"
              id="respondent-search"
              type="search"
              placeholder="Name, member ID or city"
              value={search}
              onChange={(event) => filter("search", event.target.value)}
            />
          </Field>
          <Field id="respondent-source" label="Source">
            <select
              className="select"
              id="respondent-source"
              value={params.get("source_id") || ""}
              onChange={(event) => filter("source_id", event.target.value)}
            >
              <option value="">All sources</option>
              {filters.sources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.name}
                </option>
              ))}
            </select>
          </Field>
          <Field id="respondent-city" label="City">
            <select
              className="select"
              id="respondent-city"
              value={params.get("city") || ""}
              onChange={(event) => filter("city", event.target.value)}
            >
              <option value="">All cities</option>
              {filters.cities.map((city) => (
                <option key={city} value={city}>
                  {city}
                </option>
              ))}
            </select>
          </Field>
          <Field id="respondent-status" label="Status">
            <select
              className="select"
              id="respondent-status"
              value={params.get("status") || ""}
              onChange={(event) => filter("status", event.target.value)}
            >
              <option value="">All statuses</option>
              {filters.statuses.map((status) => (
                <option key={status} value={status}>
                  {status.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="filter-actions">
          <span className="field-help" role="status">
            {resource.loading || search !== delayedSearch
              ? "Updating results…"
              : `${rows.length} matching member${rows.length === 1 ? "" : "s"}`}
          </span>
          {params.size > 0 && (
            <button
              className="text-button"
              onClick={() => setParams({}, { replace: true })}
            >
              Clear filters
            </button>
          )}
        </div>
        <ResourceError staff error={resource.error} retry={resource.reload} />
        <Notice kind="error">{exportError}</Notice>
        <div
          className="table-wrap"
          tabIndex="0"
          role="region"
          aria-label="Respondent search results"
          aria-busy={resource.loading}
        >
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Member</th>
                <th scope="col">City</th>
                <th scope="col">Source</th>
                <th scope="col">Status</th>
                <th scope="col">Profile</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((member) => (
                <tr key={member.id}>
                  <td>
                    <Link
                      className="subtle-link"
                      to={`/admin/respondents/${member.id}`}
                      state={{
                        returnTo: `${location.pathname}${location.search}`,
                      }}
                    >
                      {member.name || "Unnamed member"}
                    </Link>
                    <small>
                      #{member.id} · {member.phone}
                    </small>
                  </td>
                  <td>{member.city || "Not provided"}</td>
                  <td>{member.source?.name || "Not recorded"}</td>
                  <td>
                    <Status value={member.status} />
                  </td>
                  <td>
                    {member.profile_complete ? "Complete" : "Needs details"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {resource.loading && !resource.data ? (
          <Loading>Loading respondents…</Loading>
        ) : (
          !resource.error &&
          rows.length === 0 && (
            <div className="empty-inline">
              <h3>No matching respondents</h3>
              <p className="muted">
                Try a different search or clear the filters.
              </p>
            </div>
          )
        )}
      </section>
    </div>
  );
}

function ClaimReview({ member, onAction, busy }) {
  const [query, setQuery] = useState("");
  const delayed = useDebounced(query);
  const matches = useResource(
    delayed.trim()
      ? `/admin/respondents?search=${encodeURIComponent(delayed.trim())}`
      : null,
  );
  const [referrerId, setReferrerId] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");
  const referral = member.referral;
  function verify(event) {
    event.preventDefault();
    onAction(
      `/admin/referrals/${referral.id}/review`,
      { referrer_member_id: Number(referrerId) },
      "Referral claim verified.",
    );
  }
  function reject(event) {
    event.preventDefault();
    onAction(
      `/admin/referrals/${referral.id}/review`,
      { failure_reason: rejectionReason.trim() },
      "Referral claim rejected with a reason.",
    );
  }
  return (
    <section className="card panel-stack">
      <h2>Review named referral claim</h2>
      <p className="muted">
        Claimed referrer:{" "}
        <strong>{referral.claimed_name || "Not provided"}</strong>. Verifying a
        referrer keeps this member’s acquisition source unchanged.
      </p>
      <Field
        id="referrer-search"
        label="Find the referring member"
        help="Search by name, member ID or city, then choose a result."
      >
        <input
          className="input"
          id="referrer-search"
          type="search"
          placeholder="Search members"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </Field>
      <ResourceError staff error={matches.error} retry={matches.reload} />
      {matches.loading ? (
        <p className="field-help" role="status">
          Searching members…
        </p>
      ) : (
        delayed.trim() &&
        matches.data && (
          <div className="member-search-results">
            {matches.data.respondents
              .filter((candidate) => candidate.id !== member.id)
              .slice(0, 8)
              .map((candidate) => (
                <button
                  className={`member-mini ${String(candidate.id) === referrerId ? "selected" : ""}`}
                  key={candidate.id}
                  onClick={() => setReferrerId(String(candidate.id))}
                  type="button"
                >
                  <strong>{candidate.name || "Unnamed member"}</strong>
                  <span>
                    Member #{candidate.id} ·{" "}
                    {candidate.city || "City not provided"}
                  </span>
                </button>
              ))}
            {matches.data.respondents.filter(
              (candidate) => candidate.id !== member.id,
            ).length === 0 && (
              <p className="field-help">
                No other members matched. Try a name or enter the member ID
                below.
              </p>
            )}
          </div>
        )
      )}
      <form className="form-stack" onSubmit={verify}>
        <Field
          id="referrer-id"
          label="Referrer member ID"
          help="Use the selected member above, or enter a known member ID. Self-referral is not allowed."
        >
          <input
            className="input"
            id="referrer-id"
            type="number"
            min="1"
            step="1"
            required
            value={referrerId}
            onChange={(event) => setReferrerId(event.target.value)}
          />
        </Field>
        <button
          className="button"
          disabled={busy || Number(referrerId) === member.id}
        >
          {busy ? "Saving…" : "Verify referral"}
        </button>
      </form>
      <form className="form-stack claim-reject-form" onSubmit={reject}>
        <Field id="claim-reason" label="Reason for rejecting this claim">
          <textarea
            className="textarea"
            id="claim-reason"
            required
            minLength={3}
            maxLength={1000}
            rows="2"
            value={rejectionReason}
            onChange={(event) => setRejectionReason(event.target.value)}
          />
        </Field>
        <button className="button button-secondary" disabled={busy}>
          {busy ? "Saving…" : "Reject claim"}
        </button>
      </form>
    </section>
  );
}

function Participation({ participation, onAction, busy }) {
  const [fullyCompleted, setFullyCompleted] = useState(false);
  const [qualityPassed, setQualityPassed] = useState(false);
  const canFit =
    participation.eligibility_status === "approved" &&
    !participation.fit_at &&
    !participation.completed_at;
  const canComplete =
    participation.eligibility_status === "approved" &&
    participation.fit_at &&
    !participation.completed_at;
  return (
    <article className="participation-card panel-stack">
      <div className="section-heading">
        <h3>{participation.survey_title}</h3>
        <Status
          value={
            participation.completed_at
              ? "completed"
              : participation.fit_at
                ? "fit"
                : participation.eligibility_status
          }
        />
      </div>
      <p className="field-help">
        Application #{participation.id} · Survey #{participation.survey_id}
      </p>
      {participation.fit_at && (
        <p className="field-help">
          Fit recorded: {formatDate(participation.fit_at, true)}
        </p>
      )}
      {participation.completed_at && (
        <p className="field-help">
          QC completion recorded: {formatDate(participation.completed_at, true)}
        </p>
      )}
      {canFit && (
        <>
          <p className="muted">
            Confirm that this approved member matches the survey requirements.
          </p>
          <button
            className="button button-secondary"
            disabled={busy}
            onClick={() =>
              onAction(
                `/admin/participations/${participation.id}/fit`,
                undefined,
                "Member marked Fit for this survey.",
              )
            }
          >
            {busy ? "Saving…" : "Mark Fit"}
          </button>
        </>
      )}
      {canComplete && (
        <>
          <fieldset className="fieldset panel-stack">
            <legend className="field-label">Completion confirmation</legend>
            <label className="checkbox-line">
              <input
                type="checkbox"
                checked={fullyCompleted}
                onChange={(event) => setFullyCompleted(event.target.checked)}
              />
              The member completed the full survey.
            </label>
            <label className="checkbox-line">
              <input
                type="checkbox"
                checked={qualityPassed}
                onChange={(event) => setQualityPassed(event.target.checked)}
              />
              The member passed the quality check.
            </label>
          </fieldset>
          <button
            className="button"
            disabled={busy || !fullyCompleted || !qualityPassed}
            onClick={() =>
              onAction(
                `/admin/participations/${participation.id}/complete`,
                undefined,
                "Survey completion recorded after quality check. The member’s three-month cool-off now applies.",
              )
            }
          >
            {busy ? "Saving…" : "Mark Completed after QA"}
          </button>
        </>
      )}
    </article>
  );
}

export function RespondentDetail() {
  const { id } = useParams();
  const location = useLocation();
  const resource = useResource(`/admin/respondents/${encodeURIComponent(id)}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [failureReason, setFailureReason] = useState("");
  async function action(path, body, message) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await api(path, { method: "POST", body });
      setSuccess(message);
      resource.reload();
    } catch (err) {
      setError(err.message);
      resource.reload();
    } finally {
      setBusy(false);
    }
  }
  const member = resource.data;
  const referral = member?.referral;
  return (
    <div className="workspace-page">
      <Link
        className="back-link"
        to={location.state?.returnTo || "/admin/respondents"}
      >
        ← Back to respondents
      </Link>
      <ResourceError staff error={resource.error} retry={resource.reload} />
      <Notice kind="error">{error}</Notice>
      <Notice kind="success">{success}</Notice>
      {resource.loading ? (
        <Loading>Loading member details…</Loading>
      ) : (
        member && (
          <>
            <div className="workspace-heading">
              <div>
                <p className="eyebrow">RESPONDENT #{member.id}</p>
                <h1 className="page-title">
                  {member.name || "Unnamed member"}
                </h1>
                <p className="muted">
                  {member.phone} · {member.city || "City not provided"}
                </p>
              </div>
              <Status value={member.status} />
            </div>
            <div className="two-column">
              <div className="panel-stack">
                <section className="card">
                  <h2>Member details</h2>
                  <dl className="detail-grid">
                    <div className="detail-item">
                      <dt>Signup source</dt>
                      <dd>{member.source?.name || "Not recorded"}</dd>
                    </div>
                    <div className="detail-item">
                      <dt>Profile</dt>
                      <dd>
                        {member.profile_complete ? "Complete" : "Needs details"}
                      </dd>
                    </div>
                  </dl>
                </section>
                <section className="card panel-stack">
                  <h2>Survey participation</h2>
                  {member.participations?.length ? (
                    member.participations.map((participation) => (
                      <Participation
                        key={participation.id}
                        participation={participation}
                        busy={busy}
                        onAction={action}
                      />
                    ))
                  ) : (
                    <p className="muted">
                      No survey applications yet. A member must apply before
                      staff can mark Fit or Completed.
                    </p>
                  )}
                </section>
              </div>
              <div className="panel-stack">
                <section className="card panel-stack">
                  <h2>Referral information</h2>
                  {referral ? (
                    <>
                      <div className="action-row">
                        <Status value={referral.stage} />
                        <Status value={referral.verification_status} />
                      </div>
                      {referral.referrer && (
                        <p className="muted">
                          Referred by{" "}
                          <Link
                            to={`/admin/respondents/${referral.referrer.id}`}
                          >
                            {referral.referrer.name || "Member"} (#
                            {referral.referrer.id})
                          </Link>
                        </p>
                      )}
                      {referral.claimed_name && (
                        <p className="field-help">
                          Name entered at signup: {referral.claimed_name}
                        </p>
                      )}
                      {referral.failure_reason && (
                        <Notice kind="warning">
                          Reason: {referral.failure_reason}
                        </Notice>
                      )}
                      {referral.verification_status === "verified" &&
                        !referral.failure_reason &&
                        referral.stage !== "completed" && (
                          <form
                            className="form-stack"
                            onSubmit={(event) => {
                              event.preventDefault();
                              action(
                                `/admin/referrals/${referral.id}/fail`,
                                { reason: failureReason.trim() },
                                "Referral marked failed with a visible reason.",
                              );
                            }}
                          >
                            <Field
                              id="referral-failure"
                              label="Referral failure reason"
                              help="This reason will be visible to the referring member."
                            >
                              <textarea
                                className="textarea"
                                id="referral-failure"
                                rows="3"
                                required
                                minLength={3}
                                maxLength={1000}
                                value={failureReason}
                                onChange={(event) =>
                                  setFailureReason(event.target.value)
                                }
                              />
                            </Field>
                            <button
                              className="button button-secondary"
                              disabled={busy}
                            >
                              {busy ? "Saving…" : "Mark referral failed"}
                            </button>
                          </form>
                        )}
                    </>
                  ) : (
                    <p className="muted">
                      This member has no referral or named claim.
                    </p>
                  )}
                </section>
                {referral?.verification_status === "pending" && (
                  <ClaimReview
                    key={referral.id}
                    member={member}
                    onAction={action}
                    busy={busy}
                  />
                )}
              </div>
            </div>
          </>
        )
      )}
    </div>
  );
}
