import { afterEach, beforeEach, describe, expect, it } from "vitest";
import MockAdapter from "axios-mock-adapter";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { apiClient } from "../src/services/apiClient";
import AdminSystemStatusPage from "../src/pages/admin/AdminSystemStatusPage";

let api: MockAdapter;
beforeEach(() => { api = new MockAdapter(apiClient); });
afterEach(() => api.restore());
const status = {
  status: "degraded", backend: { status: "up", connections: { rustfs: { status: "up" }, rabbitmq_consumer: { status: "down" } } },
  databases: { auth_db: { status: "up" }, medical_db: { status: "down" }, audit_db: { status: "up" } },
  preprocessing: { status: "ok", connections: { rustfs: { status: "ok" }, rabbitmq: { status: "ok" } } },
  ml: { status: "degraded", connections: { database: { status: "up" }, rabbitmq_consumer: { status: "down" }, rabbitmq_publisher: { status: "up" } } },
};
describe("system status", () => {
  it("renders diagnostics including backend connections", async () => {
    api.onGet("/storage/usage").reply(200, { status: "available", bucket: "eeg", bucket_exists: true, used_bytes: 1024, object_count: 2 });
    api.onGet("/admin/system-status").reply(200, status);
    render(<AdminSystemStatusPage />);
    expect(await screen.findByText("eeg")).toBeInTheDocument();
    expect(await screen.findByText(/Overall status:/)).toHaveTextContent("Degraded");
    const list = screen.getByLabelText("Connection statuses");
    expect(within(list).getByText(/Backend to Medical DB.*disconnected/)).toBeInTheDocument();
    expect(within(list).getByText(/RabbitMQ to ML service.*disconnected/)).toBeInTheDocument();
    expect(within(list).getByText(/Preprocessing to RustFS.*connected/)).toBeInTheDocument();
    expect(within(list).getByText(/Backend to RustFS.*connected/)).toBeInTheDocument();
    expect(within(list).getByText(/RabbitMQ to Backend.*disconnected/)).toBeInTheDocument();
  });
  it.each([
    ["up", "connected"],
    ["down", "disconnected"],
    ["unknown", "unknown"],
  ])("maps backend connection status %s to %s", async (backendStatus, expected) => {
    api.onGet("/storage/usage").reply(503);
    api.onGet("/admin/system-status").reply(200, {
      ...status,
      backend: { status: "up", connections: { rustfs: { status: backendStatus }, rabbitmq_consumer: { status: backendStatus } } },
    });
    render(<AdminSystemStatusPage />);
    await screen.findByText(/Overall status:/);
    const list = screen.getByLabelText("Connection statuses");
    expect(within(list).getByText(new RegExp(`Backend to RustFS.*: ${expected}\\.`))).toBeInTheDocument();
    expect(within(list).getByText(new RegExp(`RabbitMQ to Backend.*: ${expected}\\.`))).toBeInTheDocument();
  });
  it("keeps missing backend diagnostics unknown", async () => {
    api.onGet("/storage/usage").reply(503);
    api.onGet("/admin/system-status").reply(200, { ...status, backend: { status: "up", connections: {} } });
    render(<AdminSystemStatusPage />);
    await screen.findByText(/Overall status:/);
    const list = screen.getByLabelText("Connection statuses");
    expect(within(list).getByText(/Backend to RustFS.*: unknown/)).toBeInTheDocument();
    expect(within(list).getByText(/RabbitMQ to Backend.*: unknown/)).toBeInTheDocument();
  });
  it("shows failures and permits retry", async () => {
    api.onGet("/storage/usage").reply(503);
    api.onGet("/admin/system-status").replyOnce(503).onGet("/admin/system-status").reply(200, status);
    const user = userEvent.setup();
    render(<AdminSystemStatusPage />);
    expect(await screen.findByText("System status is unavailable. Try refreshing.")).toBeInTheDocument();
    expect(await screen.findByText("Storage usage is unavailable.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(await screen.findByText(/Overall status:/)).toHaveTextContent("Degraded");
  });
});
