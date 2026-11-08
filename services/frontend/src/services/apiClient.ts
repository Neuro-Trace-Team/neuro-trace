import axios, {
  type AxiosError,
  type InternalAxiosRequestConfig,
} from "axios";

type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

type RetriableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
};

const backendBaseUrl = import.meta.env.VITE_BACKEND_URL?.replace(/\/+$/, "") ?? "";
const apiBaseUrl = `${backendBaseUrl}/api/v1`;

export const backendClient = axios.create({ baseURL: backendBaseUrl });
export const apiClient = axios.create({ baseURL: apiBaseUrl });

let refreshRequest: Promise<TokenResponse> | null = null;

function clearStoredSession() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  window.dispatchEvent(new Event("auth:expired"));
}

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableRequestConfig | undefined;
    const isAuthRequest = /\/auth\/(login|refresh|logout)$/.test(config?.url ?? "");
    const refreshToken = localStorage.getItem("refresh_token");

    if (error.response?.status !== 401 || !config || config._retry || isAuthRequest) {
      return Promise.reject(error);
    }

    config._retry = true;
    if (!refreshToken) {
      clearStoredSession();
      return Promise.reject(error);
    }

    refreshRequest ??= axios
      .post<TokenResponse>(`${apiBaseUrl}/auth/refresh`, {
        refresh_token: refreshToken,
      })
      .then(({ data }) => data)
      .finally(() => {
        refreshRequest = null;
      });

    try {
      const tokens = await refreshRequest;
      localStorage.setItem("access_token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);
      config.headers.Authorization = `Bearer ${tokens.access_token}`;
      return await apiClient(config);
    } catch (refreshError) {
      if (axios.isAxiosError(refreshError) && refreshError.response?.status === 401) {
        clearStoredSession();
      }
      return Promise.reject(refreshError);
    }
  },
);

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) {
    return fallback;
  }

  const detail = error.response?.data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item: { msg?: unknown }) =>
        typeof item.msg === "string" ? item.msg : "",
      )
      .filter(Boolean)
      .join(", ");
  }

  return error.message || fallback;
}
