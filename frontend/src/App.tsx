import { useEffect, useState } from "react";

type Connection = "checking" | "connected" | "unavailable";

export function App() {
  const [connection, setConnection] = useState<Connection>("checking");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 5000);
    let active = true;

    async function checkConnection() {
      try {
        const response = await fetch("/api/health", {
          signal: controller.signal,
        });
        if (!response.ok)
          throw new Error(`Health request ${attempt + 1} failed.`);
        const body: unknown = await response.json();
        if (
          typeof body !== "object" ||
          body === null ||
          !("status" in body) ||
          body.status !== "ok" ||
          !("service" in body) ||
          body.service !== "ai-data-investigator"
        )
          throw new Error("Unexpected health response.");
        if (active) setConnection("connected");
      } catch {
        if (active) setConnection("unavailable");
      } finally {
        window.clearTimeout(timeout);
      }
    }

    void checkConnection();
    return () => {
      active = false;
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [attempt]);

  const status = {
    checking: "Checking API connection…",
    connected: "API connected",
    unavailable: "API unavailable. Start the backend, then retry.",
  }[connection];

  return (
    <main>
      <header>
        <a className="wordmark" href="/">
          AI Data Investigator
        </a>
        <span className="stage">Project foundation · v0.0.1</span>
      </header>

      <section className="intro" aria-labelledby="title">
        <p className="eyebrow">From a dataset to a finding you can verify</p>
        <h1 id="title">
          Understand the data.
          <br />
          Inspect the evidence.
        </h1>
        <p className="description">
          We’re building an assistant that profiles CSV files, investigates your
          questions with SQL, and connects every finding to its supporting
          results.
        </p>
        <div className="connection" role="status" aria-live="polite">
          <span className={`indicator ${connection}`} aria-hidden="true" />
          <span>{status}</span>
          {connection === "unavailable" && (
            <button
              type="button"
              onClick={() => {
                setConnection("checking");
                setAttempt((value) => value + 1);
              }}
            >
              Retry connection
            </button>
          )}
        </div>
      </section>

      <section className="workflow" aria-labelledby="workflow-title">
        <div className="section-title">
          <h2 id="workflow-title">The investigation workflow</h2>
          <span>Coming in the next milestones</span>
        </div>
        <ol>
          <li>
            <span className="step">01</span>
            <h3>Explore a CSV</h3>
            <p>
              Inspect columns, missing values, and distributions before asking a
              question.
            </p>
          </li>
          <li>
            <span className="step">02</span>
            <h3>Ask and refine</h3>
            <p>
              Compare a metric across categories or time, then narrow the
              investigation.
            </p>
          </li>
          <li>
            <span className="step">03</span>
            <h3>Verify a finding</h3>
            <p>
              Read the chart, SQL, filters, and computed results behind the
              answer.
            </p>
          </li>
        </ol>
      </section>

      <aside className="example" aria-labelledby="example-title">
        <p className="eyebrow">First planned investigation</p>
        <h2 id="example-title">“How did monthly revenue change by region?”</h2>
        <p>Synthetic sales data · monthly totals · regional comparison</p>
      </aside>
      <footer>
        Development foundation. Uploads and analytical investigations arrive in
        later milestones.
      </footer>
    </main>
  );
}
