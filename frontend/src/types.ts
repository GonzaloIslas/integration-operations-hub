export type PaymentStatus = "pending" | "succeeded" | "failed" | "refunded";

export interface Refund {
  id: string;
  amount: string;
  status: string;
  created_at: string;
}

export interface Payment {
  id: string;
  amount: string;
  currency: string;
  provider: string;
  status: PaymentStatus;
  correlation_id: string;
  provider_reference: string | null;
  failure_code: string | null;
  failure_message: string | null;
  retryable: boolean | null;
  created_at: string;
  updated_at: string;
  refunds: Refund[];
}

export interface OperationLog {
  id: string;
  event_type: string;
  detail: string | null;
  created_at: string;
}

export interface Integration {
  name: string;
  display_name: string;
  description: string;
    is_simulated: boolean;
}

export interface DashboardSummary {
  total_payments: number;
  successful_payments: number;
  failed_payments: number;
  refunded_payments: number;
  success_rate: number;
  error_rate: number;
  retryable_failures: number;
  average_latency_ms: number | null;
}

export interface ProviderHealth {
  name: string;
  display_name: string;
  health: "healthy" | "degraded" | "down" | "unknown";
  total_payments: number;
  success_rate: number;
  error_rate: number;
  average_latency_ms: number | null;
  retryable_failures: number;
}

export interface DashboardData {
  summary: DashboardSummary;
  providers: ProviderHealth[];
  recent_payments: Payment[];
  recent_failures: Payment[];
}
