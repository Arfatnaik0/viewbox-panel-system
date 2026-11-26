import { useContext } from "react";
import {
  Link,
  NavLink,
  Navigate,
  Outlet,
  useNavigate,
  useOutletContext,
} from "react-router-dom";
import { api } from "./api.js";
import { SessionContext } from "./session.js";
import { Loading, Notice, ResourceError, useResource } from "./portal-ui.jsx";
import { useState } from "react";

export function StaffLayout() {
  const session = useResource("/admin/session");
  const { setMember } = useContext(SessionContext);
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function logout() {
    setBusy(true);
    setError("");
    try {
      await api("/auth/logout", { method: "POST" });
      setMember(null);
      navigate("/admin/login", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  if (session.loading) return <Loading>Checking your staff session…</Loading>;
  if (session.error?.status === 401)
    return <Navigate to="/admin/login" replace />;
  if (session.error)
    return <ResourceError staff error={session.error} retry={session.reload} />;
  return (
    <>
      <div className="staff-session">
        <span>
          {session.data.email}{" "}
          <span className="role-label">{session.data.role}</span>
        </span>
        <button className="text-button" onClick={logout} disabled={busy}>
          {busy ? "Logging out…" : "Log out"}
        </button>
      </div>
      <nav className="portal-nav" aria-label="Staff navigation">
        <NavLink to="/admin/respondents">Respondents</NavLink>
        <NavLink to="/admin/import">Import CSV</NavLink>
        <NavLink to="/admin/dashboard">Source dashboard</NavLink>
        {session.data.role === "admin" && (
          <>
            <NavLink to="/admin/surveys">Surveys</NavLink>
            <NavLink to="/admin/sources">Signup sources</NavLink>
          </>
        )}
      </nav>
      <Notice kind="error">{error}</Notice>
      <Outlet context={session.data} />
    </>
  );
}

export function AdminOnly({ children }) {
  const session = useOutletContext();
  return session?.role === "admin" ? (
    children
  ) : (
    <section className="card">
      <h1 className="card-title">Admin access required</h1>
      <p className="muted">
        Your staff account can manage respondents, referral reviews and source
        reporting.
      </p>
      <Link className="button button-secondary" to="/admin/respondents">
        Open respondents
      </Link>
    </section>
  );
}

export function MemberNavigation() {
  return (
    <nav className="portal-nav member-nav" aria-label="Member navigation">
      <NavLink to="/home">Home</NavLink>
      <NavLink to="/surveys">Surveys</NavLink>
      <NavLink to="/referrals">My referrals</NavLink>
    </nav>
  );
}
