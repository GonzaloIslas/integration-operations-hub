import type { CopilotExplanation, DashboardData, Integration, OperationInspection, OperationLog, Payment, RetryJob } from "./types";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const credentialsStorageKey = "integration-operations-hub.operator-credentials";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string): Promise<T> {
  const credentials = sessionStorage.getItem(credentialsStorageKey);
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: credentials ? { Authorization: `Basic ${credentials}` } : undefined
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new ApiError(body?.detail ?? `Request failed with ${response.status}.`, response.status);
  }
  return response.json() as Promise<T>;
}

async function post<T>(path: string, body: object = {}): Promise<T> {
  const credentials = sessionStorage.getItem(credentialsStorageKey);
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(credentials ? { Authorization: `Basic ${credentials}` } : {})
    },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new ApiError(payload?.detail ?? `Request failed with ${response.status}.`, response.status);
  }
  return response.json() as Promise<T>;
}

export function hasOperatorCredentials() {
  return Boolean(sessionStorage.getItem(credentialsStorageKey));
}

export function setOperatorCredentials(username: string, password: string) {
  sessionStorage.setItem(credentialsStorageKey, btoa(`${username}:${password}`));
}

export function clearOperatorCredentials() {
  sessionStorage.removeItem(credentialsStorageKey);
}

export const getPayments = () => request<Payment[]>("/payments");
export const getDashboard = () => request<DashboardData>("/dashboard");
export const getPayment = (paymentId: string) => request<Payment>(`/payments/${paymentId}`);
export const getPaymentOperations = (paymentId: string) => request<OperationLog[]>(`/payments/${paymentId}/operations`);
export const getPaymentInspections = (paymentId: string) => request<OperationInspection[]>(`/payments/${paymentId}/inspections`);
export const getPaymentRetries = (paymentId: string) => request<RetryJob[]>(`/payments/${paymentId}/retries`);
export const queuePaymentRetry = (paymentId: string) => post<RetryJob>(`/payments/${paymentId}/retry`);
export const askCopilot = (paymentId: string, question: string) => post<CopilotExplanation>(`/payments/${paymentId}/copilot`, { question });
export const getIntegrations = () => request<Integration[]>("/integrations");
export const getIntegration = (integrationName: string) => request<Integration>(`/integrations/${integrationName}`);
