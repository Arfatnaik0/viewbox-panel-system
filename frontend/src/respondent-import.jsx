import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "./api.js";
import { Field, Notice, ResourceError } from "./portal-ui.jsx";

const MAX_FILE_BYTES = 2 * 1024 * 1024;

function ImportSummary({ report }) {
  const labels = [
    ["total", "Total rows"],
    ["created", report.preview ? "To create" : "Created"],
    ["matched", report.preview ? "To match" : "Matched"],
    ["fixed", "Fixed"],
    ["skipped", "Skipped"],
  ];
  return (
    <dl className="import-summary">
      {labels.map(([key, label]) => (
        <div key={key}>
          <dt>{label}</dt>
          <dd>{report.summary[key]}</dd>
        </div>
      ))}
    </dl>
  );
}

function RowReport({ issues }) {
  return (
    <section className="panel-stack" aria-labelledby="row-report-title">
      <h3 id="row-report-title">Fixes, skipped rows and notices</h3>
      {issues.length ? (
        <>
          <p className="field-help">
            Review each reason before proceeding. Rows marked skipped will not
            create a new member.
          </p>
          <div
            className="table-wrap import-report"
            tabIndex="0"
            role="region"
            aria-label="CSV row report"
          >
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Row</th>
                  <th scope="col">Action</th>
                  <th scope="col">Reason</th>
                </tr>
              </thead>
              <tbody>
                {issues.map((issue, index) => (
                  <tr key={`${issue.row}-${issue.action}-${index}`}>
                    <th scope="row">{issue.row > 0 ? issue.row : "File"}</th>
                    <td>
                      <span className={`status-badge status-${issue.action}`}>
                        {issue.action}
                      </span>
                    </td>
                    <td>{issue.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="muted">
          No fixes, skipped rows or notices were reported.
        </p>
      )}
    </section>
  );
}

export default function RespondentImport() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [pending, setPending] = useState(null);
  const [error, setError] = useState(null);
  const [fileError, setFileError] = useState("");
  const [lastOperation, setLastOperation] = useState("preview");
  const fileInput = useRef(null);
  const reportHeading = useRef(null);
  const report = result || preview;

  useEffect(() => {
    if (report) reportHeading.current?.focus();
  }, [report]);

  function selectFile(event) {
    const selected = event.target.files?.[0] || null;
    setPreview(null);
    setResult(null);
    setError(null);
    setFileError("");
    if (selected?.size === 0) {
      setFile(null);
      setFileError(
        "This file is empty. Choose a CSV that contains respondent rows.",
      );
      return;
    }
    if (selected?.size > MAX_FILE_BYTES) {
      setFile(null);
      setFileError(
        "This file is larger than 2 MiB. Split it into smaller CSV files, then preview one at a time.",
      );
      return;
    }
    setFile(selected);
  }

  function clear() {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    setFileError("");
    if (fileInput.current) {
      fileInput.current.value = "";
      fileInput.current.focus();
    }
  }

  async function run(operation) {
    if (!file || pending || (operation === "import" && (!preview || result)))
      return;
    setPending(operation);
    setLastOperation(operation);
    setError(null);
    const payload = new FormData();
    payload.append("file", file, file.name);
    try {
      const dryRun = operation === "preview";
      const response = await api(
        `/admin/imports/respondents?preview=${dryRun}`,
        { method: "POST", body: payload },
      );
      if (
        !response?.summary ||
        !Array.isArray(response.issues) ||
        response.preview !== dryRun
      )
        throw new Error(
          "The import service returned an unexpected response. Please try again.",
        );
      if (dryRun) setPreview(response);
      else setResult(response);
    } catch (err) {
      setError(err);
    } finally {
      setPending(null);
    }
  }

  const importable =
    preview && preview.summary.created + preview.summary.matched > 0;

  return (
    <div className="workspace-page">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">RESPONDENT DATA</p>
          <h1 className="page-title">Import respondents</h1>
          <p className="muted">
            Preview a CSV, review repairs and skipped rows, then import the same
            selected file.
          </p>
        </div>
        <Link
          className="button button-secondary button-small"
          to="/admin/respondents"
        >
          View respondents
        </Link>
      </div>
      <div className="import-layout">
        <section
          className="card panel-stack"
          aria-labelledby="choose-file-title"
        >
          <h2 id="choose-file-title">1. Choose and preview</h2>
          <p className="muted">
            Select your respondent CSV. Safe formatting repairs are reported;
            bad rows are skipped so the rest can be processed.
          </p>
          <Notice kind="error">{fileError}</Notice>
          <form
            className="form-stack"
            onSubmit={(event) => {
              event.preventDefault();
              run("preview");
            }}
          >
            <Field
              id="respondent-csv"
              label="Respondent CSV file"
              help="UTF-8 CSV with a phone column; up to 2 MiB and 5,000 rows. Example: viewbox_respondents_sample.csv."
            >
              <input
                className="input file-input"
                ref={fileInput}
                id="respondent-csv"
                name="file"
                type="file"
                accept=".csv,text/csv"
                required
                disabled={Boolean(pending)}
                onChange={selectFile}
                aria-describedby="respondent-csv-help"
              />
            </Field>
            {file && (
              <p className="field-help selected-file">
                Selected: <strong>{file.name}</strong> ·{" "}
                {Math.max(1, Math.ceil(file.size / 1024))} KB
              </p>
            )}
            <div className="import-file-actions">
              <button
                className="button"
                type="submit"
                disabled={!file || Boolean(pending) || Boolean(result)}
              >
                {pending === "preview" ? "Previewing CSV…" : "Preview CSV"}
              </button>
              {file && (
                <button
                  className="text-button"
                  type="button"
                  onClick={clear}
                  disabled={Boolean(pending)}
                >
                  Choose another file
                </button>
              )}
            </div>
          </form>
          <p className="field-help">
            Preview does not save members. Changing the selected file clears the
            previous preview.
          </p>
        </section>
        <section
          className="card panel-stack"
          aria-labelledby="save-import-title"
        >
          <h2 id="save-import-title">2. Review and import</h2>
          {result ? (
            <Notice kind="success">
              Import finished. Review the result below or open respondents to
              inspect the saved members.
            </Notice>
          ) : preview ? (
            <>
              <p className="muted">
                The preview below is for{" "}
                <strong className="file-name">{file?.name}</strong>. Import uses
                that same selected file.
              </p>
              {importable ? (
                <button
                  className="button"
                  type="button"
                  onClick={() => run("import")}
                  disabled={Boolean(pending)}
                >
                  {pending === "import"
                    ? "Importing respondents…"
                    : "Import selected CSV"}
                </button>
              ) : (
                <Notice kind="warning">
                  No valid rows are available to import. Review the skipped-row
                  reasons, correct the CSV and preview it again.
                </Notice>
              )}
              <p className="field-help">
                Existing members are matched instead of being created again. The
                final result reflects the data present when the import runs.
              </p>
            </>
          ) : (
            <p className="muted">
              Choose a file and select Preview CSV to see the totals and row
              report here before saving.
            </p>
          )}
        </section>
      </div>
      <div className="import-feedback" aria-live="polite">
        {pending && (
          <p className="field-help" role="status">
            <span className="spinner" aria-hidden="true" />
            {pending === "preview"
              ? "Checking the selected CSV. No members are being saved."
              : "Importing the selected CSV. Please wait for the result."}
          </p>
        )}
      </div>
      <ResourceError staff error={error} retry={() => run(lastOperation)} />
      {report && (
        <section
          className="card import-result panel-stack"
          aria-labelledby="import-report-heading"
        >
          <div className="section-heading">
            <div>
              <p className="step-label">
                {report.preview
                  ? "PREVIEW ONLY · NOT SAVED"
                  : "IMPORT FINISHED"}
              </p>
              <h2 id="import-report-heading" ref={reportHeading} tabIndex="-1">
                {report.preview ? "Import preview" : "Import result"}
              </h2>
            </div>
            <span className="file-name field-help">{file?.name}</span>
          </div>
          <ImportSummary report={report} />
          <RowReport issues={report.issues} />
          {result && (
            <Link className="button button-secondary" to="/admin/respondents">
              View respondents
            </Link>
          )}
        </section>
      )}
    </div>
  );
}
