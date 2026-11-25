import { useState } from "react";
import { api } from "./api.js";
import { GENDERS, INCOMES, INTERESTS } from "./profile-options.js";
import {
  Field,
  formatDate,
  Loading,
  Notice,
  ResourceError,
  Status,
  useResource,
} from "./portal-ui.jsx";

const RULE_FIELDS = [
  ["age", "Age range"],
  ["city", "City"],
  ["gender", "Gender"],
  ["income_range", "Monthly income (INR)"],
];
function localDateTime(date) {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
function initialForm() {
  const now = new Date();
  return {
    title: "",
    description: "",
    opens_at: localDateTime(now),
    closes_at: localDateTime(new Date(now.getTime() + 14 * 86400000)),
    quota: "20",
    published: false,
    interests: [],
  };
}
function newRule(field = "age") {
  return {
    key: crypto.randomUUID(),
    field,
    mode: "strict",
    min: "18",
    max: "65",
    text: "",
    values: [],
  };
}

function RuleEditor({ rule, index, update, remove, usedFields }) {
  const prefix = `rule-${rule.key}`;
  const choices = rule.field === "gender" ? GENDERS : INCOMES;
  function toggle(value) {
    update({
      values: rule.values.includes(value)
        ? rule.values.filter((item) => item !== value)
        : [...rule.values, value],
    });
  }
  return (
    <fieldset className="rule-row">
      <legend className="rule-label">Rule {index + 1}</legend>
      <div className="rule-grid">
        <Field id={`${prefix}-field`} label="Profile field">
          <select
            className="select"
            id={`${prefix}-field`}
            value={rule.field}
            onChange={(event) =>
              update({ field: event.target.value, values: [], text: "" })
            }
          >
            {RULE_FIELDS.map(([value, label]) => (
              <option
                value={value}
                key={value}
                disabled={value !== rule.field && usedFields.includes(value)}
              >
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field id={`${prefix}-mode`} label="Rule strength">
          <select
            className="select"
            id={`${prefix}-mode`}
            value={rule.mode}
            onChange={(event) => update({ mode: event.target.value })}
          >
            <option value="strict">Strict · reject on mismatch</option>
            <option value="flexible">Flexible · waitlist on mismatch</option>
          </select>
        </Field>
      </div>
      {rule.field === "age" ? (
        <div className="form-grid">
          <Field id={`${prefix}-min`} label="Minimum age">
            <input
              className="input"
              id={`${prefix}-min`}
              type="number"
              min="0"
              max="120"
              required
              value={rule.min}
              onChange={(event) => update({ min: event.target.value })}
            />
          </Field>
          <Field id={`${prefix}-max`} label="Maximum age">
            <input
              className="input"
              id={`${prefix}-max`}
              type="number"
              min="0"
              max="120"
              required
              value={rule.max}
              onChange={(event) => update({ max: event.target.value })}
            />
          </Field>
        </div>
      ) : rule.field === "city" ? (
        <Field
          id={`${prefix}-cities`}
          label="Allowed cities"
          help="Separate multiple cities with commas."
        >
          <input
            className="input"
            id={`${prefix}-cities`}
            required
            value={rule.text}
            onChange={(event) => update({ text: event.target.value })}
            placeholder="Bengaluru, Mumbai"
          />
        </Field>
      ) : (
        <div
          className="choice-grid"
          role="group"
          aria-label={`Allowed ${rule.field === "gender" ? "genders" : "income ranges"}`}
        >
          {choices.map(([value, label]) => (
            <label
              className={`choice ${rule.values.includes(value) ? "choice-selected" : ""}`}
              key={value}
            >
              <input
                className="choice-input"
                type="checkbox"
                checked={rule.values.includes(value)}
                onChange={() => toggle(value)}
              />
              {label}
            </label>
          ))}
        </div>
      )}
      <button
        className="text-button remove-button"
        type="button"
        onClick={remove}
      >
        Remove rule {index + 1}
      </button>
    </fieldset>
  );
}

export default function AdminSurveys() {
  const resource = useResource("/admin/surveys");
  const [form, setForm] = useState(initialForm);
  const [rules, setRules] = useState([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [publishing, setPublishing] = useState(null);
  function change(event) {
    setForm((current) => ({
      ...current,
      [event.target.name]:
        event.target.type === "checkbox"
          ? event.target.checked
          : event.target.value,
    }));
  }
  function updateRule(key, patch) {
    setRules((current) =>
      current.map((rule) => (rule.key === key ? { ...rule, ...patch } : rule)),
    );
  }
  function addRule() {
    const field = RULE_FIELDS.find(
      ([value]) => !rules.some((rule) => rule.field === value),
    )?.[0];
    if (field) setRules((current) => [...current, newRule(field)]);
  }
  async function create(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    const start = new Date(form.opens_at),
      end = new Date(form.closes_at);
    if (!(end > start) || end - start > 15 * 86400000) {
      setError(
        "The closing date must follow the opening date, with a survey cycle of no more than 15 days.",
      );
      return;
    }
    const serializedRules = rules.map((rule) => ({
      field: rule.field,
      mode: rule.mode,
      values:
        rule.field === "age"
          ? [Number(rule.min), Number(rule.max)]
          : rule.field === "city"
            ? [
                ...new Set(
                  rule.text
                    .split(",")
                    .map((city) => city.trim())
                    .filter(Boolean),
                ),
              ]
            : rule.values,
    }));
    if (
      serializedRules.some(
        (rule) =>
          rule.values.length === 0 ||
          (rule.field === "age" && rule.values[0] > rule.values[1]),
      )
    ) {
      setError(
        "Each rule needs an allowed value. Age minimum must not exceed its maximum.",
      );
      return;
    }
    setBusy(true);
    try {
      const created = await api("/admin/surveys", {
        method: "POST",
        body: {
          ...form,
          title: form.title.trim(),
          description: form.description.trim(),
          opens_at: start.toISOString(),
          closes_at: end.toISOString(),
          quota: Number(form.quota),
          rules: serializedRules,
        },
      });
      setSuccess(
        `“${created.title}” was created${created.published ? " and published" : " as a draft"}.`,
      );
      setForm(initialForm());
      setRules([]);
      resource.reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function publish(survey) {
    setPublishing(survey.id);
    setError("");
    setSuccess("");
    try {
      await api(`/admin/surveys/${survey.id}/publish`, {
        method: "PATCH",
        body: { published: !survey.published },
      });
      setSuccess(
        `“${survey.title}” ${survey.published ? "was unpublished" : "is published"}.`,
      );
      resource.reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setPublishing(null);
    }
  }
  return (
    <div className="workspace-page">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">SURVEY MANAGEMENT</p>
          <h1 className="page-title">Surveys</h1>
          <p className="muted">
            Create a research window of up to 15 days, set eligibility rules and
            publish when ready.
          </p>
        </div>
      </div>
      <Notice kind="error">{error}</Notice>
      <Notice kind="success">{success}</Notice>
      <div className="two-column survey-admin-layout">
        <section className="card">
          <h2>Create a survey</h2>
          <form className="form-stack" onSubmit={create}>
            <Field id="survey-title" label="Survey title">
              <input
                className="input"
                id="survey-title"
                name="title"
                value={form.title}
                onChange={change}
                required
                maxLength={200}
              />
            </Field>
            <Field id="survey-description" label="Description">
              <textarea
                className="textarea"
                id="survey-description"
                name="description"
                rows="3"
                value={form.description}
                onChange={change}
                maxLength={3000}
              />
            </Field>
            <div className="form-grid">
              <Field id="survey-opens" label="Opens at (local time)">
                <input
                  className="input"
                  id="survey-opens"
                  name="opens_at"
                  type="datetime-local"
                  required
                  value={form.opens_at}
                  onChange={change}
                />
              </Field>
              <Field id="survey-closes" label="Closes at (local time)">
                <input
                  className="input"
                  id="survey-closes"
                  name="closes_at"
                  type="datetime-local"
                  required
                  value={form.closes_at}
                  onChange={change}
                />
              </Field>
            </div>
            <Field
              id="survey-quota"
              label="Participant quota"
              help="Only approved applications reserve a place."
            >
              <input
                className="input"
                id="survey-quota"
                name="quota"
                type="number"
                min="1"
                max="100000"
                required
                value={form.quota}
                onChange={change}
              />
            </Field>
            <fieldset className="fieldset">
              <legend className="field-label">Interest highlights</legend>
              <p className="field-help">
                Optional. Matching interests highlight the survey; they do not
                override eligibility.
              </p>
              <div className="choice-grid">
                {INTERESTS.map((interest) => (
                  <label
                    className={`choice ${form.interests.includes(interest) ? "choice-selected" : ""}`}
                    key={interest}
                  >
                    <input
                      className="choice-input"
                      type="checkbox"
                      checked={form.interests.includes(interest)}
                      onChange={() =>
                        setForm((current) => ({
                          ...current,
                          interests: current.interests.includes(interest)
                            ? current.interests.filter(
                                (value) => value !== interest,
                              )
                            : [...current.interests, interest],
                        }))
                      }
                    />
                    {interest}
                  </label>
                ))}
              </div>
            </fieldset>
            <div>
              <div className="section-heading">
                <h3>Eligibility rules</h3>
                <button
                  className="text-button"
                  type="button"
                  onClick={addRule}
                  disabled={rules.length === RULE_FIELDS.length}
                >
                  + Add rule
                </button>
              </div>
              {rules.length === 0 && (
                <p className="field-help">
                  No profile restrictions added. Quota, deadline and cool-off
                  checks still apply.
                </p>
              )}
              <div className="panel-stack">
                {rules.map((rule, index) => (
                  <RuleEditor
                    key={rule.key}
                    rule={rule}
                    index={index}
                    usedFields={rules.map((item) => item.field)}
                    update={(patch) => updateRule(rule.key, patch)}
                    remove={() =>
                      setRules((current) =>
                        current.filter((item) => item.key !== rule.key),
                      )
                    }
                  />
                ))}
              </div>
            </div>
            <label className="checkbox-line">
              <input
                type="checkbox"
                name="published"
                checked={form.published}
                onChange={change}
              />
              Publish immediately
            </label>
            <button className="button" disabled={busy}>
              {busy ? "Creating survey…" : "Create survey"}
            </button>
          </form>
        </section>
        <section className="panel-stack">
          <div className="section-heading">
            <h2>Existing surveys</h2>
            <span className="count-badge">{resource.data?.length ?? "—"}</span>
          </div>
          <ResourceError staff error={resource.error} retry={resource.reload} />
          {resource.loading ? (
            <Loading>Loading surveys…</Loading>
          ) : (
            !resource.error &&
            (resource.data?.length ? (
              resource.data.map((survey) => (
                <article className="card survey-card" key={survey.id}>
                  <div className="section-heading">
                    <h3>{survey.title}</h3>
                    <Status value={survey.published ? "published" : "draft"} />
                  </div>
                  <p className="muted">{survey.description}</p>
                  <p className="survey-meta">
                    {formatDate(survey.opens_at, true)} →{" "}
                    {formatDate(survey.closes_at, true)}
                  </p>
                  <p className="field-help">
                    Quota: {survey.quota} · {survey.rules?.length || 0} profile
                    rules
                  </p>
                  <button
                    className="button button-secondary button-small"
                    type="button"
                    onClick={() => publish(survey)}
                    disabled={publishing !== null}
                  >
                    {publishing === survey.id
                      ? "Saving…"
                      : survey.published
                        ? "Unpublish"
                        : "Publish"}
                  </button>
                </article>
              ))
            ) : (
              <div className="card empty-inline">
                <h3>No surveys created yet</h3>
                <p className="muted">
                  Create your first survey using the form.
                </p>
              </div>
            ))
          )}
        </section>
      </div>
    </div>
  );
}
