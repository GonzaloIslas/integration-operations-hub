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
