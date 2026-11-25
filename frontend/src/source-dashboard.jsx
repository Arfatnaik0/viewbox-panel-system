import { Loading, ResourceError, useResource } from "./portal-ui.jsx";

export default function SourceDashboard() {
  const resource = useResource("/admin/source-stats");
  const sources = resource.data || [];
  const sum = (field) =>
    sources.reduce((total, source) => total + Number(source[field] || 0), 0);
  return (
    <div className="workspace-page">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">SOURCE REPORTING</p>
          <h1 className="page-title">Source dashboard</h1>
          <p className="muted">
            See how each acquisition source contributes signups, survey Fit and
            quality-checked completions.
          </p>
        </div>
        <button
          className="button button-secondary button-small"
          disabled={resource.loading}
          onClick={resource.reload}
        >
          Refresh counts
        </button>
      </div>
      <ResourceError staff error={resource.error} retry={resource.reload} />
      {resource.loading ? (
        <Loading>Loading source counts…</Loading>
      ) : (
        !resource.error && (
          <>
            <div className="metrics-grid">
              {[
                ["Signups", sum("signups")],
                ["Fit", sum("fit")],
                ["Completed", sum("completed")],
              ].map(([label, value]) => (
                <section className="card metric-card" key={label}>
                  <h2>{label}</h2>
                  <p className="metric-value">{value}</p>
                </section>
              ))}
            </div>
            <section className="card">
              <h2>Counts by source</h2>
              <p className="field-help">
                Each milestone counts distinct members within a source.
                Acquisition source is separate from referral credit.
              </p>
              <div
                className="table-wrap"
                tabIndex="0"
                role="region"
                aria-label="Source milestone counts"
              >
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Source</th>
                      <th scope="col">Signups</th>
                      <th scope="col">Fit</th>
                      <th scope="col">Completed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sources.map((source) => (
                      <tr key={source.id}>
                        <th scope="row">{source.name}</th>
                        <td>{source.signups}</td>
                        <td>{source.fit}</td>
                        <td>{source.completed}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {sources.length === 0 && (
                <div className="empty-inline">
                  <p className="muted">No sources are available yet.</p>
                </div>
              )}
            </section>
          </>
        )
      )}
    </div>
  );
}
