import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "./api.js";

export function Notice({ children, kind = "info" }) {
  return children ? (
    <div
      className={`notice notice-${kind}`}
      role={kind === "error" ? "alert" : "status"}
    >
      {children}
    </div>
  ) : null;
}

export function Loading({ children = "Loading…" }) {
  return (
    <div className="loading-state" role="status">
      <span className="spinner" aria-hidden="true" />
      {children}
    </div>
  );
}

export function Field({ label, id, help, children }) {
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

export function Status({ value }) {
  return (
    <span className={`status-badge status-${value || "pending"}`}>
      {String(value || "pending").replaceAll("_", " ")}
    </span>
  );
}

export function formatDate(value, time = false) {
  if (!value) return "—";
  const date = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
        ...(time ? { hour: "2-digit", minute: "2-digit" } : {}),
      });
}

export function useResource(path, { keepPrevious = false } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(Boolean(path));
  const [error, setError] = useState(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!path) {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    if (!keepPrevious) setData(null);
    api(path, { signal: controller.signal })
      .then(setData)
      .catch((err) => {
        if (err.name !== "AbortError") setError(err);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [path, revision, keepPrevious]);
  return {
    data,
    setData,
    loading,
    error,
    reload: () => setRevision((value) => value + 1),
  };
}

export function useDebounced(value, delay = 250) {
  const [delayed, setDelayed] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDelayed(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return delayed;
}

export function ResourceError({ error, retry, staff = false }) {
  if (!error) return null;
  return (
    <Notice kind="error">
      {error.message}{" "}
      {error.status === 401 ? (
        <Link to={staff ? "/admin/login" : "/"}>Sign in again</Link>
      ) : (
        <button className="inline-button" type="button" onClick={retry}>
          Try again
        </button>
      )}
    </Notice>
  );
}

export function Eligibility({ eligibility }) {
  if (!eligibility) return null;
  return (
    <div className="reason-box">
      <Status value={eligibility.status} />
      <p>{eligibility.reason}</p>
      {eligibility.eligible_on && (
        <p className="reason-date">
          Next eligible date:{" "}
          <strong>{formatDate(eligibility.eligible_on)}</strong>
        </p>
      )}
    </div>
  );
}
