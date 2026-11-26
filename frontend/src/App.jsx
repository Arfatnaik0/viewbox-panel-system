import { useContext, useEffect, useRef, useState } from "react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import { api } from "./api.js";

import { SessionContext } from "./session.js";
import { GENDERS, INCOMES, INTERESTS } from "./profile-options.js";
import { MemberSurveys, MyReferrals, SurveyDetail } from "./member-pages.jsx";
import { AdminOnly, MemberNavigation, StaffLayout } from "./staff-layout.jsx";
import AdminSurveys from "./admin-surveys.jsx";
import { RespondentDetail, Respondents } from "./admin-respondents.jsx";
import SourceDashboard from "./source-dashboard.jsx";
import RespondentImport from "./respondent-import.jsx";
import "./operations.css";

const SOURCE_STORAGE = "viewbox.signup-source";

function storedToken() {
  try {
    return sessionStorage.getItem(SOURCE_STORAGE);
  } catch {
    return null;
  }
}

function rememberToken(token) {
  try {
    sessionStorage.setItem(SOURCE_STORAGE, token);
  } catch {
    /* Signup still works without browser storage. */
  }
}

function forgetToken() {
  try {
    sessionStorage.removeItem(SOURCE_STORAGE);
  } catch {
    /* Browser storage is optional. */
  }
}

function SessionProvider({ children }) {
  const [member, setMember] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState("");
  useEffect(() => {
    let alive = true;
    api("/member/me")
      .then((data) => {
        if (alive) setMember(data);
      })
      .catch((error) => {
        if (alive && error.status !== 401) setSessionError(error.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);
  return (
    <SessionContext.Provider
      value={{ member, setMember, loading, sessionError }}
    >
      {children}
    </SessionContext.Provider>
  );
}

function Loading({ message = "Getting things ready…" }) {
  return (
    <div className="loading-state" role="status">
      <span className="spinner" aria-hidden="true" />
      {message}
    </div>
  );
}

function Notice({ children, kind = "info" }) {
  if (!children) return null;
  return (
    <div
      className={`notice notice-${kind}`}
      role={kind === "error" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}

function Field({ label, id, help, children }) {
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      {children}
      {help && (
        <p className="field-help" id={`${id}-help`}>
          {help}
        </p>
      )}
    </div>
  );
}

function Header() {
  const { member, setMember } = useContext(SessionContext);
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function logout() {
    setBusy(true);
    setError("");
    try {
      await api("/auth/logout", { method: "POST" });
      setMember(null);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <header className="site-header">
        <Link
          className="brand"
          to={member ? "/home" : "/"}
          aria-label="ViewBox Club home"
        >
          <span className="brand-mark" aria-hidden="true">
            v<span>•</span>
          </span>
          <span className="brand-copy">
            <span className="brand-name">
              viewbox<span>club</span>
            </span>
            <span className="brand-caption">Member portal</span>
          </span>
        </Link>
        <nav className="nav-actions" aria-label="Main navigation">
          {pathname.startsWith("/admin") ? (
            <Link className="text-button" to="/">
              Member portal <span aria-hidden="true">↗</span>
            </Link>
          ) : member ? (
            <button className="text-button" onClick={logout} disabled={busy}>
              {busy ? "Logging out…" : "Log out"}
            </button>
          ) : (
            <Link className="text-button" to="/admin/login">
              Staff login <span aria-hidden="true">↗</span>
            </Link>
          )}
        </nav>
      </header>
      {error && (
        <div className="header-notice">
          <Notice kind="error">{error}</Notice>
        </div>
      )}
    </>
  );
}

function Story({ staff = false }) {
  return (
    <section
      className="auth-story"
      aria-label={staff ? "Staff portal introduction" : "Welcome to ViewBox"}
    >
      <p className="eyebrow">
        {staff ? "STAFF PORTAL" : "VIEWBOX MEMBER PORTAL"}
      </p>
      <h1 className="story-title">
        {staff ? (
          <>
            Manage research.
            <br />
            <span>Track progress.</span>
          </>
        ) : (
          <>
            Your profile.
            <br />
            <span>Your connections.</span>
          </>
        )}
      </h1>
      <p className="story-copy">
        {staff
          ? "Review respondents, record survey progress and understand which sources bring members."
          : "Bring your perspective to the conversation. Start with your profile, then share ViewBox with the people you know."}
      </p>
      <div className="story-art" aria-hidden="true">
        <div className="art-window">
          <span />
          <span />
          <span />
          <span />
        </div>
        <div className="art-label">
          {staff ? "Signup source tracking" : "Your ViewBox membership"}
        </div>
        <div className="art-spark">✳</div>
      </div>
      <div className="trust-note">
        <span aria-hidden="true">◌</span>
        {staff
          ? "Your sources and signup links, together."
          : "Sign in. Complete your profile. Share your link."}
      </div>
    </section>
  );
}

function Login() {
  const { token: routeToken } = useParams();
  const { member, setMember, loading, sessionError } =
    useContext(SessionContext);
  const navigate = useNavigate();
  const [phone, setPhone] = useState("");
  const [referrerName, setReferrerName] = useState("");
  const [challenge, setChallenge] = useState(null);
  const [code, setCode] = useState("");
  const [link, setLink] = useState(null);
  const [linkLoading, setLinkLoading] = useState(true);
  const [linkNotice, setLinkNotice] = useState("");
  const [sourceRequired, setSourceRequired] = useState(false);
  const [sources, setSources] = useState([]);
  const [sourceId, setSourceId] = useState("");
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceError, setSourceError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setLink(null);
    setLinkNotice("");
    setLinkLoading(true);
    async function resolve() {
      const remembered = storedToken();
      const candidate = routeToken || remembered;
      if (!candidate) {
        if (alive) setLinkLoading(false);
        return;
      }
      try {
        const data = await api(
          `/signup/links/${encodeURIComponent(candidate)}`,
        );
        if (alive) {
          setLink({ ...data, token: candidate });
          rememberToken(candidate);
        }
      } catch (err) {
        if (!alive) return;
        if (err.status !== 404)
          setLinkNotice(
            "We could not check your signup link. Try reloading before you continue, or choose your source when asked.",
          );
        else if (routeToken && remembered && routeToken !== remembered) {
          try {
            const previous = await api(
              `/signup/links/${encodeURIComponent(remembered)}`,
            );
            if (alive) {
              setLink({ ...previous, token: remembered });
              setLinkNotice(
                "This link is unavailable. Your previous signup source is still attached.",
              );
            }
          } catch {
            if (alive)
              setLinkNotice(
                "This signup link is unavailable. You can still join and choose how you heard about us.",
              );
          }
        } else
          setLinkNotice(
            "This signup link is unavailable. You can still join and choose how you heard about us.",
          );
      } finally {
        if (alive) setLinkLoading(false);
      }
    }
    resolve();
    return () => {
      alive = false;
    };
  }, [routeToken]);

  async function loadSources() {
    setSourceLoading(true);
    setSourceError("");
    try {
      setSources(await api("/signup/sources"));
    } catch (err) {
      setSourceError(err.message);
    } finally {
      setSourceLoading(false);
    }
  }
  useEffect(() => {
    if (sourceRequired) loadSources();
  }, [sourceRequired]);

  async function requestCode(event) {
    event?.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await api("/auth/otp/request", {
        method: "POST",
        body: { phone: phone.trim() },
      });
      setChallenge(data);
      setCode("");
      setSourceRequired(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function verifyCode(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const body = { challenge_id: challenge.challenge_id, code: code.trim() };
    if (link) body.source_token = link.token;
    if (sourceId) body.source_id = Number(sourceId);
    if (referrerName.trim() && !link?.personal)
      body.referrer_name = referrerName.trim();
    try {
      const data = await api("/auth/otp/verify", { method: "POST", body });
      forgetToken();
      setMember(data);
      navigate(data.profile_complete ? "/home" : "/profile", { replace: true });
    } catch (err) {
      if (err.detail?.code === "source_required") {
        setSourceRequired(true);
        setError("");
      } else if (err.detail?.code === "invalid_source_link") {
        forgetToken();
        setLink(null);
        setSourceId("");
        setSourceRequired(true);
        setError("");
        setLinkNotice(
          "Your signup link is no longer available. Choose how you heard about ViewBox to continue.",
        );
      } else setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Loading />;
  if (member)
    return (
      <Navigate to={member.profile_complete ? "/home" : "/profile"} replace />
    );
  return (
    <div className="auth-layout">
      <Story />
      <section className="auth-card" aria-labelledby="login-title">
        <div className="card-header">
          <p className="step-label">
            {challenge ? "PHONE VERIFICATION" : "MEMBER SIGN IN"}
          </p>
          <h2 className="card-title" id="login-title">
            {challenge ? "Check your code." : "Let’s get you in."}
          </h2>
          <p className="muted">
            {challenge ? (
              <>
                Enter the code for <strong>{phone}</strong>.
              </>
            ) : (
              "New here or coming back? Start with your phone number."
            )}
          </p>
        </div>
        {sessionError && <Notice kind="warning">{sessionError}</Notice>}
        {linkNotice && <Notice kind="warning">{linkNotice}</Notice>}
        {link && (
          <div className="source-badge">
            <span aria-hidden="true">↗</span>
            {link.personal
              ? "Your referral link is connected"
              : `Joining through ${link.source.name}`}
          </div>
        )}
        {linkLoading && (
          <p className="field-help" role="status">
            Checking your signup link…
          </p>
        )}
        <Notice kind="error">{error}</Notice>
        {!challenge ? (
          <form className="form-stack" onSubmit={requestCode}>
            <Field
              id="phone"
              label="Phone number"
              help="Enter a 10-digit Indian number or include a country code, such as +91."
            >
              <input
                className="input"
                id="phone"
                name="phone"
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                placeholder="e.g. +91 98765 43210"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                maxLength={24}
                aria-describedby="phone-help"
              />
            </Field>
            {!link?.personal && (
              <Field
                id="referrer"
                label={
                  <>
                    Referred by someone?{" "}
                    <span className="optional">Optional</span>
                  </>
                }
                help="Enter their name. Our team will check the referral."
              >
                <input
                  className="input"
                  id="referrer"
                  name="referrer_name"
                  autoComplete="off"
                  placeholder="Their name"
                  value={referrerName}
                  onChange={(e) => setReferrerName(e.target.value)}
                  maxLength={120}
                  aria-describedby="referrer-help"
                />
              </Field>
            )}
            <button
              className="button"
              type="submit"
              disabled={busy || linkLoading}
            >
              {busy ? (
                "Sending your code…"
              ) : (
                <>
                  Continue with phone <span aria-hidden="true">→</span>
                </>
              )}
            </button>
            <p className="field-help centered">
              A demo code appears on the next screen. No SMS needed.
            </p>
          </form>
        ) : (
          <form className="form-stack" onSubmit={verifyCode}>
            <div className="demo-code">
              <span>YOUR DEMO CODE</span>
              <strong>{challenge.demo_code}</strong>
              <small>Use this code to try the member portal.</small>
            </div>
            <Field id="otp" label="Verification code">
              <input
                className="input otp-code"
                id="otp"
                name="code"
                autoFocus
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="Enter code"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                required
                maxLength={8}
              />
            </Field>
            {sourceRequired && (
              <>
                <Notice>
                  One last thing: tell us how you heard about ViewBox to finish
                  creating your account.
                </Notice>
                <Field id="source" label="How did you hear about us?">
                  <select
                    className="select"
                    id="source"
                    value={sourceId}
                    onChange={(e) => setSourceId(e.target.value)}
                    required
                    disabled={sourceLoading}
                  >
                    <option value="">
                      {sourceLoading ? "Loading sources…" : "Choose a source"}
                    </option>
                    {sources.map((source) => (
                      <option key={source.id} value={source.id}>
                        {source.name}
                      </option>
                    ))}
                  </select>
                </Field>
                {sourceError && (
                  <Notice kind="error">
                    {sourceError}{" "}
                    <button
                      className="inline-button"
                      type="button"
                      onClick={loadSources}
                    >
                      Try again
                    </button>
                  </Notice>
                )}
                {!sourceLoading && !sourceError && sources.length === 0 && (
                  <Notice kind="warning">
                    No signup sources are available yet. Please contact the
                    ViewBox team.
                  </Notice>
                )}
              </>
            )}
            <button
              className="button"
              type="submit"
              disabled={busy || sourceLoading || linkLoading}
            >
              {busy ? "Checking your code…" : "Verify & continue"}
            </button>
            <div className="form-actions">
              <button
                className="text-button"
                type="button"
                onClick={() => {
                  setChallenge(null);
                  setError("");
                  setSourceRequired(false);
                }}
                disabled={busy}
              >
                Change number
              </button>
              <button
                className="text-button"
                type="button"
                onClick={requestCode}
                disabled={busy}
              >
                Send a new code
              </button>
            </div>
          </form>
        )}
        <div className="card-footnote">
          <span aria-hidden="true">⌑</span> Your profile stays connected to your
          phone number.
        </div>
      </section>
    </div>
  );
}

function MemberGuard({ children, complete = false }) {
  const { member, loading } = useContext(SessionContext);
  if (loading) return <Loading />;
  if (!member) return <Navigate to="/" replace />;
  if (complete && !member.profile_complete)
    return <Navigate to="/profile" replace />;
  return children;
}

function Profile() {
  const { member, setMember } = useContext(SessionContext);
  const navigate = useNavigate();
  const interestChoices = [
    ...new Set([...INTERESTS, ...(member.interests || [])]),
  ];
  const [form, setForm] = useState({
    name: member.name || "",
    date_of_birth: member.date_of_birth || "",
    gender: member.gender || "",
    city: member.city || "",
    income_range: member.income_range || "",
    interests: member.interests || [],
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function update(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }
  function toggleInterest(interest) {
    setForm((current) => ({
      ...current,
      interests: current.interests.includes(interest)
        ? current.interests.filter((item) => item !== interest)
        : [...current.interests, interest],
    }));
  }
  async function save(event) {
    event.preventDefault();
    setError("");
    if (!form.interests.length) {
      setError(
        "Choose at least one interest so we can get to know your preferences.",
      );
      return;
    }
    setBusy(true);
    try {
      const data = await api("/member/profile", {
        method: "PUT",
        body: { ...form, name: form.name.trim(), city: form.city.trim() },
      });
      setMember(data);
      navigate("/home", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  const today = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 10);
  return (
    <div className="profile-layout">
      <aside className="profile-intro">
        <p className="eyebrow">
          {member.profile_complete ? "YOUR MEMBER PROFILE" : "PROFILE SETUP"}
        </p>
        <h1 className="page-title">
          A little about <em>you.</em>
        </h1>
        <p className="muted">
          Your details help us understand your perspective and match you with
          relevant research.
        </p>
        <div className="profile-note">
          <span aria-hidden="true">✳</span>
          <p>
            One profile, all in one place.
            <br />
            <strong>You can update it whenever you need.</strong>
          </p>
        </div>
        {member.source && (
          <div className="source-badge">
            Signup source: {member.source.name}
          </div>
        )}
      </aside>
      <section className="card profile-card" aria-labelledby="profile-title">
        <div className="card-header">
          <p className="step-label">
            {member.profile_complete
              ? "UPDATE YOUR DETAILS"
              : "COMPLETE YOUR PROFILE"}
          </p>
          <h2 className="card-title" id="profile-title">
            {member.profile_complete
              ? "Edit your profile"
              : "Let’s get to know you."}
          </h2>
        </div>
        <Notice kind="error">{error}</Notice>
        <form className="form-stack" onSubmit={save}>
          <Field id="name" label="Full name">
            <input
              className="input"
              id="name"
              name="name"
              autoComplete="name"
              value={form.name}
              onChange={update}
              required
              maxLength={120}
            />
          </Field>
          <div className="form-row">
            <Field id="dob" label="Date of birth">
              <input
                className="input"
                id="dob"
                name="date_of_birth"
                type="date"
                autoComplete="bday"
                value={form.date_of_birth}
                onChange={update}
                required
                min="1900-01-01"
                max={today}
              />
            </Field>
            <Field id="gender" label="Gender">
              <select
                className="select"
                id="gender"
                name="gender"
                value={form.gender}
                onChange={update}
                required
              >
                <option value="">Select gender</option>
                {GENDERS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div className="form-row">
            <Field id="city" label="City">
              <input
                className="input"
                id="city"
                name="city"
                autoComplete="address-level2"
                placeholder="e.g. Bengaluru"
                value={form.city}
                onChange={update}
                required
                maxLength={100}
              />
            </Field>
            <Field id="income" label="Income range (INR)">
              <select
                className="select"
                id="income"
                name="income_range"
                value={form.income_range}
                onChange={update}
                required
              >
                <option value="">Select income range</option>
                {INCOMES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <fieldset className="fieldset">
            <legend className="field-label">What are you interested in?</legend>
            <p className="field-help">
              Choose one or more. You can always change these later.
            </p>
            <div className="choice-grid">
              {interestChoices.map((interest) => (
                <label
                  className={`choice ${form.interests.includes(interest) ? "choice-selected" : ""}`}
                  key={interest}
                >
                  <input
                    className="choice-input"
                    type="checkbox"
                    checked={form.interests.includes(interest)}
                    onChange={() => toggleInterest(interest)}
                  />
                  <span>{interest}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="profile-actions">
            <button className="button" type="submit" disabled={busy}>
              {busy ? (
                "Saving your profile…"
              ) : member.profile_complete ? (
                "Save changes"
              ) : (
                <>
                  Save & continue <span aria-hidden="true">→</span>
                </>
              )}
            </button>
            {member.profile_complete && (
              <Link className="text-button" to="/home">
                Cancel
              </Link>
            )}
          </div>
        </form>
      </section>
    </div>
  );
}

function CopyButton({ value, small = false }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  async function copy() {
    setError("");
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch {
      setError("Copy is unavailable here. Select and copy the link manually.");
    }
  }
  return (
    <div className="copy-action">
      <button
        className={`button button-secondary ${small ? "button-small" : ""}`}
        type="button"
        onClick={copy}
      >
        {copied ? "Copied ✓" : "Copy link"}
      </button>
      <span className="sr-only" role="status">
        {copied ? "Link copied to clipboard." : ""}
      </span>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

function Home() {
  const { member } = useContext(SessionContext);
  const [shareError, setShareError] = useState("");
  const referralUrl = member.referral_token
    ? `${window.location.origin}/join/${encodeURIComponent(member.referral_token)}`
    : "";
  async function share() {
    try {
      await navigator.share({
        title: "Join ViewBox Club",
        text: "Bring your perspective to ViewBox Club.",
        url: referralUrl,
      });
    } catch (err) {
      if (err.name !== "AbortError")
        setShareError(
          "Sharing did not finish. You can copy your link instead.",
        );
    }
  }
  return (
    <div className="member-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">MEMBER HOME</p>
          <h1 className="page-title">
            Hello, {member.name?.split(" ")[0] || "there"}
            <span className="coral">.</span>
          </h1>
          <p className="muted">Good to have your perspective here.</p>
        </div>
        <Link className="button button-secondary button-small" to="/profile">
          Edit profile <span aria-hidden="true">↗</span>
        </Link>
      </div>
      <div className="dashboard-grid">
        <section className="card member-card" aria-labelledby="member-details">
          <div className="member-avatar" aria-hidden="true">
            {member.name?.charAt(0).toUpperCase() || "V"}
          </div>
          <p className="step-label">YOUR MEMBER PROFILE</p>
          <h2 id="member-details">{member.name}</h2>
          <p className="muted">
            {member.city} <span aria-hidden="true">·</span> {member.phone}
          </p>
          <div className="stat-row">
            <span className="stat-label">Member ID</span>
            <span className="stat-value">#{member.id}</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Signup source</span>
            <span className="stat-value">
              {member.source?.name || "Not recorded"}
            </span>
          </div>
          <div className="profile-ready">
            <span aria-hidden="true">✓</span> Profile complete
          </div>
        </section>
        <section
          className="card referral-card"
          aria-labelledby="referral-title"
        >
          <p className="eyebrow">YOUR REFERRAL LINK</p>
          <h2 id="referral-title">Invite a friend.</h2>
          <p className="muted">
            Know someone with a point of view? Send your personal link. We’ll
            connect their signup to you.
          </p>
          {referralUrl ? (
            <>
              <label className="field-label" htmlFor="referral-link">
                Your personal referral link
              </label>
              <div className="referral-link-row">
                <input
                  className="input referral-link"
                  id="referral-link"
                  readOnly
                  value={referralUrl}
                  onFocus={(e) => e.target.select()}
                />
                <CopyButton value={referralUrl} />
              </div>
              {typeof navigator.share === "function" && (
                <button className="text-button share-button" onClick={share}>
                  Share with a friend <span aria-hidden="true">↗</span>
                </button>
              )}
              <Notice kind="error">{shareError}</Notice>
              <p className="field-help">
                A referral qualifies after your friend is a survey fit,
                completes it and passes the quality check.
              </p>
            </>
          ) : (
            <Notice kind="warning">
              Your referral link is not available yet. Please contact the
              ViewBox team.
            </Notice>
          )}
        </section>
      </div>
      <MemberSurveys embedded />
    </div>
  );
}

function AdminLogin() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function login(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/admin/login", {
        method: "POST",
        body: { email: email.trim(), password },
      });
      navigate("/admin/respondents", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-layout">
      <Story staff />
      <section className="auth-card" aria-labelledby="staff-title">
        <div className="card-header">
          <p className="step-label">VIEWBOX STAFF</p>
          <h2 className="card-title" id="staff-title">
            Back to the desk.
          </h2>
          <p className="muted">
            Sign in to manage respondents and survey progress.
          </p>
        </div>
        <Notice kind="error">{error}</Notice>
        <form className="form-stack" onSubmit={login}>
          <Field id="email" label="Work email">
            <input
              className="input"
              id="email"
              name="email"
              type="email"
              autoComplete="username"
              placeholder="you@example.com"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
          <Field id="password" label="Password">
            <input
              className="input"
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <button className="button" disabled={busy}>
            {busy ? "Signing in…" : "Sign in to staff portal"}
          </button>
        </form>
        <details className="demo-details">
          <summary>Trying the local demo?</summary>
          <p>
            Email: <code>admin@viewbox.test</code>
            <br />
            Password: <code>ViewBoxDemo!32</code>
            <br />
            Staff: <code>staff@viewbox.test</code>
            <br />
            Staff password: <code>ViewBoxStaff!32</code>
          </p>
        </details>
        <p className="card-footnote">
          Here to share your perspective?{" "}
          <Link to="/">Open the member portal</Link>
        </p>
      </section>
    </div>
  );
}

function AdminSources() {
  const navigate = useNavigate();
  const [admin, setAdmin] = useState(null);
  const [sources, setSources] = useState(null);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [success, setSuccess] = useState("");
  const sourceInput = useRef(null);
  async function load() {
    setLoading(true);
    setError("");
    try {
      const identity = await api("/admin/session");
      setAdmin(identity);
      setSources(await api("/admin/sources"));
    } catch (err) {
      if (err.status === 401 || err.status === 403)
        navigate("/admin/login", { replace: true });
      else setError(err.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  async function create(event) {
    event.preventDefault();
    setBusy(true);
    setFormError("");
    setSuccess("");
    try {
      const created = await api("/admin/sources", {
        method: "POST",
        body: { name: name.trim() },
      });
      setSources((current) => [...(current || []), created]);
      setName("");
      setSuccess(`“${created.name}” is ready. Copy its link to start sharing.`);
      sourceInput.current?.focus();
    } catch (err) {
      if (err.status === 401 || err.status === 403)
        navigate("/admin/login", { replace: true });
      else setFormError(err.message);
    } finally {
      setBusy(false);
    }
  }
  if (loading) return <Loading message="Opening your sources…" />;
  return (
    <div className="admin-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">OPERATIONS / SOURCE MANAGER</p>
          <h1 className="page-title">
            Manage signup sources
            <span className="coral">.</span>
          </h1>
          <p className="muted">
            Create a unique link for each channel. Know where your members come
            from.
          </p>
        </div>
      </div>
      {error && (
        <Notice kind="error">
          {error}{" "}
          <button type="button" className="inline-button" onClick={load}>
            Try again
          </button>
        </Notice>
      )}
      <div className="sources-layout">
        <section
          className="card create-source-card"
          aria-labelledby="create-title"
        >
          <p className="step-label">CREATE A SOURCE</p>
          <h2 id="create-title">Add a source.</h2>
          <p className="muted">
            One link per WhatsApp city group, staff member, social post or
            channel.
          </p>
          <Notice kind="error">{formError}</Notice>
          <Notice kind="success">{success}</Notice>
          <form className="form-stack" onSubmit={create}>
            <Field
              id="source-name"
              label="Source name"
              help="Choose a specific name you’ll recognize later."
            >
              <input
                className="input"
                ref={sourceInput}
                id="source-name"
                name="name"
                placeholder="e.g. WhatsApp · Bengaluru"
                required
                maxLength={100}
                value={name}
                onChange={(e) => setName(e.target.value)}
                aria-describedby="source-name-help"
              />
            </Field>
            <button
              className="button"
              disabled={busy || !admin || sources === null}
            >
              {busy ? (
                "Creating source…"
              ) : (
                <>
                  Create signup link <span aria-hidden="true">+</span>
                </>
              )}
            </button>
          </form>
          <p className="field-help source-tip">
            New channels work the same way. Add LinkedIn, a community group or
            your next campaign here.
          </p>
        </section>
        <section className="card sources-card" aria-labelledby="sources-title">
          <div className="source-list-heading">
            <div>
              <p className="step-label">READY TO SHARE</p>
              <h2 id="sources-title">Your sources</h2>
            </div>
            <span className="count-badge">{sources?.length ?? "—"}</span>
          </div>
          {sources === null ? (
            <p className="muted">
              Sources could not be loaded. Use Try again above.
            </p>
          ) : sources.length === 0 ? (
            <div className="empty-state compact">
              <div className="empty-icon" aria-hidden="true">
                ↗
              </div>
              <h3>Your first source starts here.</h3>
              <p className="muted">
                Add a source and its signup link will appear here.
              </p>
            </div>
          ) : (
            <ul className="source-list">
              {sources.map((source) => {
                const url = `${window.location.origin}/join/${encodeURIComponent(source.token)}`;
                return (
                  <li className="source-row" key={source.id}>
                    <div className="source-info">
                      <h3 className="source-name">{source.name}</h3>
                      <a className="source-url" href={url}>
                        {url}
                      </a>
                    </div>
                    <CopyButton value={url} small />
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function NotFound() {
  return (
    <section className="card not-found">
      <p className="eyebrow">PAGE NOT FOUND</p>
      <h1 className="card-title">This page isn’t here.</h1>
      <p className="muted">Head back to the member portal to find your way.</p>
      <Link className="button" to="/">
        Back to ViewBox
      </Link>
    </section>
  );
}

function MemberRouteNavigation() {
  const { member } = useContext(SessionContext);
  const { pathname } = useLocation();
  return member?.profile_complete && !pathname.startsWith("/admin") ? (
    <MemberNavigation />
  ) : null;
}

export default function App() {
  return (
    <SessionProvider>
      <div className="app-shell">
        <Header />
        <main className="main-content">
          <MemberRouteNavigation />
          <Routes>
            <Route path="/" element={<Login />} />
            <Route path="/join/:token" element={<Login />} />
            <Route
              path="/profile"
              element={
                <MemberGuard>
                  <Profile />
                </MemberGuard>
              }
            />
            <Route
              path="/home"
              element={
                <MemberGuard complete>
                  <Home />
                </MemberGuard>
              }
            />
            <Route path="/admin/login" element={<AdminLogin />} />
            <Route
              path="/surveys"
              element={
                <MemberGuard complete>
                  <MemberSurveys />
                </MemberGuard>
              }
            />
            <Route
              path="/surveys/:id"
              element={
                <MemberGuard complete>
                  <SurveyDetail />
                </MemberGuard>
              }
            />
            <Route
              path="/referrals"
              element={
                <MemberGuard complete>
                  <MyReferrals />
                </MemberGuard>
              }
            />
            <Route path="/admin" element={<StaffLayout />}>
              <Route index element={<Navigate to="respondents" replace />} />
              <Route path="respondents" element={<Respondents />} />
              <Route path="respondents/:id" element={<RespondentDetail />} />
              <Route path="import" element={<RespondentImport />} />
              <Route path="dashboard" element={<SourceDashboard />} />
              <Route
                path="surveys"
                element={
                  <AdminOnly>
                    <AdminSurveys />
                  </AdminOnly>
                }
              />
              <Route
                path="sources"
                element={
                  <AdminOnly>
                    <AdminSources />
                  </AdminOnly>
                }
              />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <footer className="footer">
          <span>ViewBox Club</span>
          <span>Your ViewBox member portal.</span>
        </footer>
      </div>
    </SessionProvider>
  );
}
