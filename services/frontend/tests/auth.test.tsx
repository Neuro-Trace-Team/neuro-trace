import { afterEach, beforeEach, describe, expect, it } from "vitest";
import MockAdapter from "axios-mock-adapter";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { apiClient, backendClient } from "../src/services/apiClient";
import { AuthProvider } from "../src/context/AuthContext";
import { ToastProvider } from "../src/context/ToastContext";
import LoginPage from "../src/pages/auth/LoginPage";
import ProtectedRoute from "../src/components/ProtectedRoute";
import RootRedirect from "../src/components/RootRedirect";

let api: MockAdapter;
let backend: MockAdapter;
beforeEach(() => { api = new MockAdapter(apiClient); backend = new MockAdapter(backendClient); });
afterEach(() => { api.restore(); backend.restore(); });
const profile = { id: "1", email: "doctor@example.com", first_name: "Anna", last_name: "Nowak", role: "DOCTOR" };

function app(path = "/auth/login") {
  return render(<MemoryRouter initialEntries={[path]}><ToastProvider><AuthProvider><Routes>
    <Route path="/" element={<RootRedirect />} />
    <Route path="/auth/login" element={<LoginPage />} />
    <Route path="/doctor" element={<ProtectedRoute allowedRoles={["doctor"]}><div>Doctor home</div></ProtectedRoute>} />
    <Route path="/admin" element={<ProtectedRoute allowedRoles={["admin"]}><div>Admin home</div></ProtectedRoute>} />
  </Routes></AuthProvider></ToastProvider></MemoryRouter>);
}

describe("authentication and route protection", () => {
  it("signs in, stores tokens and redirects by role", async () => {
    api.onPost("/auth/login").reply(200, { access_token: "access", refresh_token: "refresh" });
    backend.onGet("/api/v1/auth/me").reply(200, profile);
    const user = userEvent.setup();
    app();
    await user.type(screen.getByPlaceholderText("Email address"), profile.email);
    await user.type(screen.getByPlaceholderText("Password"), "secret123");
    await user.click(screen.getByRole("button", { name: "SIGN IN" }));
    expect(await screen.findByText("Doctor home")).toBeInTheDocument();
    expect(localStorage.getItem("access_token")).toBe("access");
    expect(localStorage.getItem("refresh_token")).toBe("refresh");
    expect(JSON.parse(api.history.post[0].data)).toEqual({ email: profile.email, password: "secret123" });
    expect(backend.history.get[0].headers?.Authorization).toBe("Bearer access");
  });
  it("shows login errors without storing a session", async () => {
    api.onPost("/auth/login").reply(400, { detail: "Invalid credentials" });
    const user = userEvent.setup();
    app();
    await user.type(screen.getByPlaceholderText("Email address"), profile.email);
    await user.type(screen.getByPlaceholderText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "SIGN IN" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid credentials");
    expect(localStorage.getItem("access_token")).toBeNull();
  });
  it("redirects an anonymous user to login", async () => {
    app("/admin");
    expect(await screen.findByRole("heading", { name: "SIGN IN" })).toBeInTheDocument();
  });
  it("restores a session and denies a route for the wrong role", async () => {
    localStorage.setItem("access_token", "existing");
    api.onGet("/auth/me").reply(200, profile);
    app("/admin");
    expect(await screen.findByText("Doctor home")).toBeInTheDocument();
    expect(screen.queryByText("Admin home")).not.toBeInTheDocument();
    await waitFor(() => expect(api.history.get[0].headers?.Authorization).toBe("Bearer existing"));
  });
});
