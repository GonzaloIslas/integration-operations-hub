import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./api", () => ({
  ApiError: class ApiError extends Error {},
  getPayments: vi.fn(),
  getIntegrations: vi.fn(),
  getPayment: vi.fn(),
  getPaymentOperations: vi.fn(),
  getIntegration: vi.fn(),
  hasOperatorCredentials: vi.fn(() => true),
  setOperatorCredentials: vi.fn(),
  clearOperatorCredentials: vi.fn()
}));

import { getIntegrations, getPayments, hasOperatorCredentials, setOperatorCredentials } from "./api";

describe("App", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  beforeEach(() => {
    vi.mocked(getPayments).mockResolvedValue([
      {
        id: "payment-1", amount: "42.00", currency: "USD", provider: "AcmePay", status: "succeeded",
        correlation_id: "correlation-1", provider_reference: "acme_1", failure_code: null, failure_message: null,
        retryable: null, created_at: "2026-09-29T12:00:00Z", updated_at: "2026-09-29T12:00:00Z", refunds: []
      }
    ]);
    vi.mocked(getIntegrations).mockResolvedValue([
      { name: "acmepay", display_name: "AcmePay", description: "Success simulator.", is_simulated: true }
    ]);
  });

  it("renders dashboard data from the API", async () => {
    render(<App />);

    await waitFor(() => expect(screen.getByText("Recent payments")).toBeInTheDocument());
    expect(screen.getByText("$42.00")).toBeInTheDocument();
    expect(screen.getByText("1 configured")).toBeInTheDocument();
    expect(screen.getAllByText("Succeeded")[0]).toBeInTheDocument();
  });

  it("shows an API error without replacing the operator view with fake data", async () => {
    vi.mocked(getPayments).mockRejectedValue(new Error("Network unavailable"));

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("The API could not be reached.");
    expect(screen.queryByText("$42.00")).not.toBeInTheDocument();
  });

  it("authenticates the operator before loading the console", async () => {
    vi.mocked(hasOperatorCredentials).mockReturnValue(false);
    render(<App />);

    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "local-development-only" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(setOperatorCredentials).toHaveBeenCalledWith("operator", "local-development-only"));
    expect(await screen.findByText("Recent payments")).toBeInTheDocument();
  });
});
