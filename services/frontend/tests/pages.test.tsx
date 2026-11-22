import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MockAdapter from "axios-mock-adapter";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { apiClient } from "../src/services/apiClient";
import { ToastProvider } from "../src/context/ToastContext";
import { AuthContext } from "../src/context/contextValue";
import AdminUsersPage from "../src/pages/admin/AdminUsersPage";
import AdminDashboardPage from "../src/pages/admin/AdminDashboardPage";
import AdminAuditLogPage from "../src/pages/admin/AdminAuditLogPage";
import DoctorDashboardPage from "../src/pages/doctor/DoctorDashboardPage";
import DoctorExaminationsPage from "../src/pages/doctor/DoctorExaminationsPage";

let api: MockAdapter;
beforeEach(() => { api = new MockAdapter(apiClient); });
afterEach(() => api.restore());
const auth = { user: { id: "doc-1", firstName: "Anna", lastName: "Nowak", email: "a@example.com", role: "doctor" as const }, login: vi.fn(), updateUser: vi.fn(), logout: vi.fn(async () => {}), isLoading: false, authError: null, checkAuthStatus: vi.fn(async () => {}) };
const wrap = (element: React.ReactNode) => render(<MemoryRouter><ToastProvider><AuthContext.Provider value={auth}>{element}</AuthContext.Provider></ToastProvider></MemoryRouter>);
const empty = { items: [], total: 0, page: 1, page_size: 20 };

describe("administrator pages", () => {
  it("creates an account with the chosen role and refreshes the list", async () => {
    api.onGet("/users").reply(200, empty);
    api.onPost("/users").reply(201, {});
    const user = userEvent.setup();
    wrap(<AdminUsersPage />);
    await screen.findByText("No matching records");
    await user.click(screen.getByRole("button", { name: "Create an Account" }));
    const dialog = screen.getByRole("dialog", { name: "Create New Account" });
    await user.type(within(dialog).getByPlaceholderText("Name"), "Jan");
    await user.type(within(dialog).getByPlaceholderText("Surname"), "Kowalski");
    await user.type(within(dialog).getByPlaceholderText("Email address"), "jan@example.com");
    await user.type(within(dialog).getByPlaceholderText("At least 12 characters"), "password12345");
    await user.click(within(dialog).getByRole("button", { name: "Admin" }));
    await user.click(within(dialog).getByRole("button", { name: "CREATE ACCOUNT" }));
    await waitFor(() => expect(api.history.post).toHaveLength(1));
    expect(JSON.parse(api.history.post[0].data)).toEqual({ first_name: "Jan", last_name: "Kowalski", email: "jan@example.com", password: "password12345", role: "ADMIN" });
    expect(await screen.findByText("User account created successfully.")).toBeInTheDocument();
    expect(api.history.get.length).toBeGreaterThanOrEqual(2);
  });
  it("loads dashboard metrics and handles independent log failure", async () => {
    api.onGet("/admin/app-activity").reply(200, { active_users_last_24h: 7, failed_login_attempts_last_24h: 2, examinations_uploaded_last_24h: 5, storage: { status: "available", bucket_exists: true, used_bytes: 1024 } });
    api.onGet("/admin/audit-logs").reply(503);
    wrap(<AdminDashboardPage />);
    expect(await screen.findByText("7")).toBeInTheDocument();
    expect(screen.getByText("1 KiB")).toBeInTheDocument();
    expect(await screen.findByText("Audit logs unavailable.")).toBeInTheDocument();
  });
  it("loads audit logs and sends pagination parameters", async () => {
    api.onGet("/admin/audit-logs").reply(200, { ...empty, items: [{ id: "log-1", created_at: "2026-01-01T00:00:00Z", event_code: "LOGIN", resource_type: "user", resource_id: "1" }], total: 1 });
    wrap(<AdminAuditLogPage />);
    expect(await screen.findByText("LOGIN")).toBeInTheDocument();
    expect(api.history.get[0].params).toMatchObject({ page: 1, page_size: 20 });
  });
});

describe("doctor pages", () => {
  it("loads recent examinations independently of patient errors", async () => {
    api.onGet("/me/recent/examinations").reply(200, [{ id: "exam-1", patient_id: "patient-1", status: "COMPLETED", examination_date: null }]);
    api.onGet("/me/recent/patients").reply(503, { detail: "Patients unavailable" });
    wrap(<DoctorDashboardPage />);
    expect(await screen.findByText("exam-1")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("Patients unavailable");
  });
  it("loads examination statuses and list", async () => {
    api.onGet("/examinations/statuses").reply(200, { statuses: ["COMPLETED"] });
    api.onGet("/examinations").reply(200, { ...empty, items: [{ id: "exam-1", patient_id: "patient-1", status: "COMPLETED", examination_date: null }], total: 1 });
    wrap(<DoctorExaminationsPage />);
    expect(await screen.findByText("exam-1")).toBeInTheDocument();
    expect(api.history.get.some((request) => request.url === "/examinations/statuses")).toBe(true);
  });
});
