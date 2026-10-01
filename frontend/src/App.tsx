import { type FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  clearOperatorCredentials,
  getDashboard,
  getIntegration,
  getIntegrations,
  getPayment,
  getPaymentOperations,
  getPayments,
  hasOperatorCredentials,
  setOperatorCredentials
} from "./api";
import type { DashboardData, Integration, OperationLog, Payment, PaymentStatus, ProviderHealth } from "./types";

type View = "dashboard" | "payments" | "integrations";

const statusLabels: Record<PaymentStatus, string> = {
  pending: "Pending",
  succeeded: "Succeeded",
  failed: "Failed",
  refunded: "Refunded"
};

function formatAmount(amount: string, currency: string) {
  return new Intl.NumberFormat("en", { style: "currency", currency }).format(Number(amount));
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function prettyDetail(detail: string | null) {
  if (!detail) return "No structured detail was recorded.";
  try {
    return JSON.stringify(JSON.parse(detail), null, 2);
  } catch {
    return detail;
  }
}

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [isAuthenticated, setIsAuthenticated] = useState(hasOperatorCredentials);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [selectedPayment, setSelectedPayment] = useState<Payment | null>(null);
  const [operations, setOperations] = useState<OperationLog[]>([]);
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null);
  const [isLoading, setIsLoading] = useState(hasOperatorCredentials);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadOverview = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [paymentData, integrationData, dashboardData] = await Promise.all([getPayments(), getIntegrations(), getDashboard()]);
      setPayments(paymentData);
      setIntegrations(integrationData);
      setDashboard(dashboardData);
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : "The API could not be reached.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) void loadOverview();
  }, [isAuthenticated]);

  const authenticate = async (username: string, password: string) => {
    setOperatorCredentials(username, password);
    setError(null);
    setIsLoading(true);
    try {
      const [paymentData, integrationData, dashboardData] = await Promise.all([getPayments(), getIntegrations(), getDashboard()]);
      setPayments(paymentData);
      setIntegrations(integrationData);
      setDashboard(dashboardData);
      setIsAuthenticated(true);
    } catch (caughtError) {
      clearOperatorCredentials();
      setError(caughtError instanceof ApiError ? caughtError.message : "The API could not be reached.");
    } finally {
      setIsLoading(false);
    }
  };

  if (!isAuthenticated) {
    return <Login isLoading={isLoading} error={error} onAuthenticate={authenticate} />;
  }

  const selectPayment = async (paymentId: string) => {
    setDetailLoading(true);
    setError(null);
    try {
      const [payment, operationData] = await Promise.all([getPayment(paymentId), getPaymentOperations(paymentId)]);
      setSelectedPayment(payment);
      setOperations(operationData);
      setView("payments");
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : "Unable to load payment details.");
    } finally {
      setDetailLoading(false);
    }
  };

  const selectIntegration = async (integrationName: string) => {
    setDetailLoading(true);
    setError(null);
    try {
      setSelectedIntegration(await getIntegration(integrationName));
      setView("integrations");
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : "Unable to load integration details.");
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">OPERATIONS CONSOLE</p>
          <h1>Integration Operations Hub</h1>
        </div>
        <button className="secondary-button" onClick={() => void loadOverview()} disabled={isLoading}>
          Refresh data
        </button>
        <button className="text-button" onClick={() => { clearOperatorCredentials(); setIsAuthenticated(false); }}>
          Sign out
        </button>
      </header>

      <nav aria-label="Primary navigation" className="navigation">
        {(["dashboard", "payments", "integrations"] as View[]).map((item) => (
          <button
            className={view === item ? "nav-item active" : "nav-item"}
            key={item}
            onClick={() => setView(item)}
          >
            {item}
          </button>
        ))}
      </nav>

      <main>
        {error && (
          <section className="error-banner" role="alert">
            <span>{error}</span>
            <button onClick={() => void loadOverview()}>Try again</button>
          </section>
        )}
        {isLoading ? (
          <p className="loading" role="status">Loading live API data…</p>
        ) : (
          <>
            {view === "dashboard" && (
              <Dashboard dashboard={dashboard} onPaymentSelect={selectPayment} />
            )}
            {view === "payments" && (
              <PaymentsView payments={payments} selectedPayment={selectedPayment} operations={operations} onSelect={selectPayment} />
            )}
            {view === "integrations" && (
              <IntegrationsView integrations={integrations} selectedIntegration={selectedIntegration} onSelect={selectIntegration} />
            )}
            {detailLoading && <p className="loading" role="status">Loading details…</p>}
          </>
        )}
      </main>
    </div>
  );
}

function Dashboard({
  dashboard,
  onPaymentSelect
}: {
  dashboard: DashboardData | null;
  onPaymentSelect: (paymentId: string) => Promise<void>;
}) {
  if (!dashboard) return <p className="empty-state">Dashboard data is not available yet.</p>;
  const { summary, providers, recent_failures: recentFailures, recent_payments: recentPayments } = dashboard;
  return (
    <>
      <section className="metric-grid" aria-label="Operational summary">
        <MetricCard label="Success rate" value={`${summary.success_rate}%`} detail={`${summary.successful_payments} successful`} />
        <MetricCard label="Error rate" value={`${summary.error_rate}%`} detail={`${summary.failed_payments} failed`} />
        <MetricCard label="Average latency" value={summary.average_latency_ms === null ? "—" : `${summary.average_latency_ms} ms`} detail="Observed provider responses" />
        <MetricCard label="Retry queue" value={String(summary.retryable_failures)} detail="Retryable failed payments" />
      </section>
      <section className="content-grid">
        <article className="panel">
          <div className="panel-heading"><h2>Recent requests</h2><span>{summary.total_payments} total</span></div>
          <PaymentTable payments={recentPayments} onSelect={onPaymentSelect} />
        </article>
        <article className="panel">
          <div className="panel-heading"><h2>Provider health</h2><span>{providers.length} monitored</span></div>
          <ProviderHealthTable providers={providers} />
        </article>
      </section>
      <section className="panel dashboard-failures">
        <div className="panel-heading"><h2>Recent failures</h2><span>{summary.failed_payments} total failures</span></div>
        <PaymentTable payments={recentFailures} onSelect={onPaymentSelect} />
      </section>
    </>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <article className="metric-card"><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

function ProviderHealthTable({ providers }: { providers: ProviderHealth[] }) {
  return <ul className="provider-health-list">{providers.map((provider) => <li key={provider.name}>
    <div><strong>{provider.display_name}</strong><span>{provider.success_rate}% success · {provider.error_rate}% error</span></div>
    <div className="provider-health-detail"><HealthBadge health={provider.health} /><small>{provider.average_latency_ms === null ? "No latency" : `${provider.average_latency_ms} ms`}</small>{provider.retryable_failures > 0 && <small>{provider.retryable_failures} retryable</small>}</div>
  </li>)}</ul>;
}

function PaymentsView({
  payments,
  selectedPayment,
  operations,
  onSelect
}: {
  payments: Payment[];
  selectedPayment: Payment | null;
  operations: OperationLog[];
  onSelect: (paymentId: string) => Promise<void>;
}) {
  return (
    <section className="split-view">
      <article className="panel"><div className="panel-heading"><h2>Payments</h2><span>Live API records</span></div><PaymentTable payments={payments} onSelect={onSelect} /></article>
      <PaymentDetail payment={selectedPayment} operations={operations} />
    </section>
  );
}

function PaymentTable({ payments, onSelect }: { payments: Payment[]; onSelect: (paymentId: string) => Promise<void> }) {
  if (!payments.length) return <p className="empty-state">No payments have been recorded yet.</p>;
  return (
    <div className="table-wrap"><table><thead><tr><th>Provider</th><th>Amount</th><th>Status</th><th>Created</th><th /></tr></thead><tbody>
      {payments.map((payment) => <tr key={payment.id}><td>{payment.provider}</td><td>{formatAmount(payment.amount, payment.currency)}</td><td><StatusBadge status={payment.status} /></td><td>{formatDate(payment.created_at)}</td><td><button className="text-button" onClick={() => void onSelect(payment.id)}>Inspect</button></td></tr>)}
    </tbody></table></div>
  );
}

function PaymentDetail({ payment, operations }: { payment: Payment | null; operations: OperationLog[] }) {
  if (!payment) return <article className="panel detail-panel"><h2>Payment details</h2><p className="empty-state">Select a payment to inspect its lifecycle and API operation records.</p></article>;
  return (
    <article className="panel detail-panel">
      <div className="panel-heading"><h2>Payment details</h2><StatusBadge status={payment.status} /></div>
      <dl className="detail-list"><dt>Amount</dt><dd>{formatAmount(payment.amount, payment.currency)}</dd><dt>Provider</dt><dd>{payment.provider}</dd><dt>Correlation ID</dt><dd className="mono">{payment.correlation_id}</dd><dt>Provider reference</dt><dd>{payment.provider_reference ?? "—"}</dd></dl>
      {payment.failure_code && <section className="failure-card"><strong>{payment.failure_code}</strong><p>{payment.failure_message}</p><span>{payment.retryable ? "Retryable" : "Not retryable"}</span></section>}
      <section><h3>Operation inspector</h3><p className="help-text">Sanitized request and provider-result context recorded by the backend.</p><ol className="operation-list">{operations.map((operation) => <li key={operation.id}><div><strong>{operation.event_type}</strong><time>{formatDate(operation.created_at)}</time></div><pre>{prettyDetail(operation.detail)}</pre></li>)}</ol></section>
    </article>
  );
}

function IntegrationsView({ integrations, selectedIntegration, onSelect }: { integrations: Integration[]; selectedIntegration: Integration | null; onSelect: (name: string) => Promise<void> }) {
  return <section className="split-view"><article className="panel"><div className="panel-heading"><h2>Integrations</h2><span>Backend catalog</span></div><ul className="integration-list">{integrations.map((integration) => <li key={integration.name}><div><strong>{integration.display_name}</strong><p>{integration.description}</p></div><button className="text-button" onClick={() => void onSelect(integration.name)}>Details</button></li>)}</ul></article><article className="panel detail-panel"><h2>Integration details</h2>{selectedIntegration ? <><dl className="detail-list"><dt>Name</dt><dd>{selectedIntegration.display_name}</dd><dt>Identifier</dt><dd className="mono">{selectedIntegration.name}</dd><dt>Mode</dt><dd>{selectedIntegration.is_simulated ? "Deterministic simulator" : "External provider"}</dd></dl><p>{selectedIntegration.description}</p></> : <p className="empty-state">Select an integration to load its details from the API.</p>}</article></section>;
}

function StatusBadge({ status }: { status: PaymentStatus }) {
  return <span className={`status-badge ${status}`}>{statusLabels[status]}</span>;
}

function HealthBadge({ health }: { health: ProviderHealth["health"] }) {
  return <span className={`health-badge ${health}`}>{health}</span>;
}

function Login({
  isLoading,
  error,
  onAuthenticate
}: {
  isLoading: boolean;
  error: string | null;
  onAuthenticate: (username: string, password: string) => Promise<void>;
}) {
  const [username, setUsername] = useState("operator");
  const [password, setPassword] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    await onAuthenticate(username, password);
  };

  return <main className="login-page"><section className="login-panel"><p className="eyebrow">OPERATIONS CONSOLE</p><h1>Integration Operations Hub</h1><p>Sign in with the local operator credentials configured for the FastAPI API.</p><form onSubmit={(event) => void submit(event)}><label>Username<input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required /></label>{submitted && error && <p className="form-error" role="alert">{error}</p>}<button className="secondary-button" disabled={isLoading}>{isLoading ? "Signing in…" : "Sign in"}</button></form><p className="help-text">This is intentionally local basic authentication. V4 will replace it with a production identity design.</p></section></main>;
}
