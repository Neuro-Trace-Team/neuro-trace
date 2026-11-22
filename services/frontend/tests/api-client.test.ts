import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import axios from "axios";
import MockAdapter from "axios-mock-adapter";
import { apiClient, getApiErrorMessage } from "../src/services/apiClient";

let api: MockAdapter;
let refresh: MockAdapter;
beforeEach(() => { api = new MockAdapter(apiClient); refresh = new MockAdapter(axios); });
afterEach(() => { api.restore(); refresh.restore(); });
describe("API client", () => {
  it("adds the access token to requests", async () => {
    localStorage.setItem("access_token", "abc");
    api.onGet("/example").reply(200, {});
    await apiClient.get("/example");
    expect(api.history.get[0].headers?.Authorization).toBe("Bearer abc");
  });
  it("refreshes expired tokens and retries the request", async () => {
    localStorage.setItem("access_token", "old");
    localStorage.setItem("refresh_token", "refresh-old");
    api.onGet("/example").replyOnce(401).onGet("/example").reply(200, { ok: true });
    refresh.onPost("/api/v1/auth/refresh").reply(200, { access_token: "new", refresh_token: "refresh-new" });
    expect((await apiClient.get("/example")).data).toEqual({ ok: true });
    expect(localStorage.getItem("refresh_token")).toBe("refresh-new");
    expect(api.history.get[1].headers?.Authorization).toBe("Bearer new");
  });
  it("clears the session when a 401 cannot be refreshed", async () => {
    localStorage.setItem("access_token", "old");
    const expired = vi.fn();
    window.addEventListener("auth:expired", expired);
    api.onGet("/example").reply(401);
    await expect(apiClient.get("/example")).rejects.toBeDefined();
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(expired).toHaveBeenCalledOnce();
    window.removeEventListener("auth:expired", expired);
  });
  it("extracts backend validation messages", () => {
    const error = new axios.AxiosError("error", undefined, undefined, undefined, { data: { detail: [{ msg: "First" }, { msg: "Second" }] }, status: 422, statusText: "", headers: {}, config: { headers: new axios.AxiosHeaders() } });
    expect(getApiErrorMessage(error, "fallback")).toBe("First, Second");
    expect(getApiErrorMessage(new Error("x"), "fallback")).toBe("fallback");
  });
});
