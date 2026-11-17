import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MockAdapter from "axios-mock-adapter";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthContext } from "../src/context/contextValue";
import { ToastProvider } from "../src/context/ToastContext";
import { apiClient } from "../src/services/apiClient";
import SettingsPage from "../src/pages/SettingsPage";
import AdminUserDetailsModal from "../src/components/AdminUserDetailsModal";
import AuditLogDetailsModal from "../src/components/AuditLogDetailsModal";

let api: MockAdapter;
const auth = { user: { id: "1", firstName: "Anna", lastName: "Nowak", email: "a@example.com", role: "doctor" as const }, login: vi.fn(), updateUser: vi.fn(), logout: vi.fn(async () => {}), isLoading: false, authError: null, checkAuthStatus: vi.fn(async () => {}) };
const profile = { id: "1", first_name: "Anna", last_name: "Nowak", email: "a@example.com", role: "DOCTOR", is_active: true };
beforeEach(() => { api = new MockAdapter(apiClient); vi.clearAllMocks(); });
afterEach(() => api.restore());
const wrap = (element: React.ReactNode) => render(<MemoryRouter initialEntries={["/settings"]}><ToastProvider><AuthContext.Provider value={auth}>{element}</AuthContext.Provider></ToastProvider></MemoryRouter>);

describe("account settings", () => {
  it("saves an edited profile field", async () => {
    api.onPatch("/users/me").reply(200, { ...profile, first_name: "Maria" });
    const user = userEvent.setup();
    wrap(<SettingsPage />);
    await user.click(screen.getByRole("button", { name: "Edit First Name" }));
    const input = screen.getByDisplayValue("Anna");
    await user.clear(input);
    await user.type(input, "Maria");
    await user.click(screen.getByRole("button", { name: "Save First Name" }));
    expect(await screen.findByText("Account details saved.")).toBeInTheDocument();
    expect(JSON.parse(api.history.patch[0].data)).toEqual({ first_name: "Maria" });
    expect(auth.updateUser).toHaveBeenCalledWith(expect.objectContaining({ firstName: "Maria" }));
  });
  it("changes the password and logs out", async () => {
    api.onPost("/auth/change-password").reply(200);
    const user = userEvent.setup();
    wrap(<Routes><Route path="/settings" element={<SettingsPage />} /><Route path="/auth/login" element={<div>Login destination</div>} /></Routes>);
    await user.type(screen.getByLabelText("Current password"), "oldpassword");
    await user.type(screen.getByLabelText("New password (at least 12 characters)"), "newpassword123");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByText("Login destination")).toBeInTheDocument();
    expect(JSON.parse(api.history.post[0].data)).toEqual({ current_password: "oldpassword", new_password: "newpassword123" });
    expect(auth.logout).toHaveBeenCalledWith(false);
  });
});

describe("administrator detail dialogs", () => {
  it("updates only changed user fields", async () => {
    api.onGet("/users/1").reply(200, profile);
    api.onPatch("/users/1").reply(200, { ...profile, is_active: false });
    const saved = vi.fn();
    const user = userEvent.setup();
    wrap(<AdminUserDetailsModal userId="1" onClose={vi.fn()} onSaved={saved} />);
    await user.click(await screen.findByRole("button", { name: "Edit user" }));
    await user.click(screen.getByLabelText("Account active"));
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(saved).toHaveBeenCalledOnce());
    expect(JSON.parse(api.history.patch[0].data)).toEqual({ is_active: false });
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });
  it("shows audit details or an API error", async () => {
    api.onGet("/admin/audit-logs/1").reply(200, { id: "1", event_code: "LOGIN", created_at: "2026-01-01T00:00:00Z", metadata: { result: "success" } });
    const view = wrap(<AuditLogDetailsModal logId="1" onClose={vi.fn()} />);
    expect(await screen.findByText("LOGIN")).toBeInTheDocument();
    expect(screen.getByText(/"result": "success"/)).toBeInTheDocument();
    view.unmount();
    api.onGet("/admin/audit-logs/2").reply(404, { detail: "Not found" });
    wrap(<AuditLogDetailsModal logId="2" onClose={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Not found");
  });
});
