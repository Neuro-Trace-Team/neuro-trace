import axios from "axios";
import { useEffect, useState } from "react";
import { backendClient, getApiErrorMessage } from "../../services/apiClient";
import PageTitle from "../../components/PageTitle";
import SectionTitle from "../../components/SectionTitle";
import Surface from "../../components/Surface";
import type { BackendReadiness } from "../../types/api.types";
import { useToast } from "../../context/useToast";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md bg-[#ffffff]/90 px-2.5 py-1">
      <p className="truncate text-[10px] text-[#193456]">{label}</p>
      <p className="truncate text-[16px] font-bold leading-5 text-[#09264d]">{value}</p>
    </div>
  );
}

function AdminDatabasePage() {
  const [readiness, setReadiness] = useState<BackendReadiness | null>(null);
  const [liveStatus, setLiveStatus] = useState("Checking");
  const [error, setError] = useState("");
  const { showToast } = useToast();

  useEffect(() => {
    backendClient
      .get<{ status: string }>("/health/live")
      .then(({ data }) => setLiveStatus(data.status))
      .catch((loadError: unknown) => {
        setLiveStatus("Unavailable");
        setError(getApiErrorMessage(loadError, "Could not reach the backend."));
        showToast(getApiErrorMessage(loadError, "Could not reach the backend."), "error");
      });

    backendClient
      .get<BackendReadiness>("/health/ready")
      .then(({ data }) => setReadiness(data))
      .catch((loadError: unknown) => {
        const responseData = axios.isAxiosError<BackendReadiness>(loadError)
          ? loadError.response?.data
          : undefined;
        if (responseData?.dependencies) {
          setReadiness(responseData);
        } else {
          setError(getApiErrorMessage(loadError, "Could not read backend readiness."));
          showToast(getApiErrorMessage(loadError, "Could not read backend readiness."), "error");
        }
      });
  }, [showToast]);

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Backend and Database Status</PageTitle>
      <div className="space-y-3">
        <Surface className="px-5 py-3">
          <SectionTitle>Service Health</SectionTitle>
          <p className="mb-3 text-sm text-[#52677b]">
            Backend liveness: <strong>{liveStatus}</strong>
          </p>
          <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-3">
            {Object.entries(readiness?.dependencies ?? {}).map(([name, status]) => (
              <Metric key={name} label={name.replaceAll("_", " ")} value={status} />
            ))}
            {!readiness && !error && <p className="text-sm text-[#52677b]">Checking dependencies...</p>}
          </div>
          {readiness && <p className="mt-3 text-sm">Overall readiness: <strong>{readiness.status}</strong></p>}
        </Surface>
        <Surface className="px-5 py-3">
          <SectionTitle>Available Monitoring</SectionTitle>
          <p className="text-sm leading-6 text-[#52677b]">
            The backend currently exposes dependency readiness only. Storage
            capacity, database usage, backup history, and model-training metrics
            are not available through its API.
          </p>
        </Surface>
      </div>
    </div>
  );
}

export default AdminDatabasePage;
