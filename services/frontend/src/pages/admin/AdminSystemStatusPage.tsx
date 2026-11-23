import { useEffect, useState } from "react";
import { apiClient } from "../../services/apiClient";
import type { SystemStatus } from "../../types/api.types";
import ButtonSecondary from "../../components/ButtonSecondary";
import PageTitle from "../../components/PageTitle";
import SectionTitle from "../../components/SectionTitle";
import Surface from "../../components/Surface";
import { useStorageUsage } from "../../hooks/useStorageUsage";
import { formatBytes } from "../../services/api";

type ConnectionStatus = "connected" | "disconnected" | "unknown";
type Connection = { from: string; to: string; label: string; path: string; status: ConnectionStatus };
type Service = { name: string; description: string; x: number; y: number; width: number; kind: "app" | "service" | "data" };

const services: Service[] = [
  { name: "Frontend", description: "APPLICATION", x: 24, y: 265, width: 140, kind: "app" },
  { name: "Backend", description: "API & ORCHESTRATION", x: 215, y: 265, width: 160, kind: "app" },
  { name: "Auth DB", description: "ACCOUNTS", x: 20, y: 45, width: 135, kind: "data" },
  { name: "Medical DB", description: "PATIENTS & EXAMS", x: 175, y: 45, width: 145, kind: "data" },
  { name: "Audit DB", description: "AUDIT LOGS", x: 340, y: 45, width: 135, kind: "data" },
  { name: "RustFS", description: "FILE STORAGE", x: 460, y: 246, width: 145, kind: "data" },
  { name: "Preprocessing", description: "EEG PROCESSING", x: 460, y: 385, width: 155, kind: "service" },
  { name: "RabbitMQ", description: "MESSAGE BROKER", x: 665, y: 385, width: 145, kind: "service" },
  { name: "ML service", description: "PREDICTIONS", x: 805, y: 195, width: 150, kind: "service" },
  { name: "Model DB", description: "ANALYSIS RESULTS", x: 805, y: 45, width: 150, kind: "data" },
];

const connectionLayout: Omit<Connection, "status">[] = [
  { from: "Frontend", to: "Backend", label: "API", path: "M164 301 H215" },
  { from: "Backend", to: "Auth DB", label: "Accounts", path: "M235 265 V225 H87 V117" },
  { from: "Backend", to: "Medical DB", label: "Examinations", path: "M295 265 V195 H247 V117" },
  { from: "Backend", to: "Audit DB", label: "Audit logs", path: "M335 265 V145 H407 V117" },
  { from: "Backend", to: "RustFS", label: "Examination files", path: "M375 282 H460" },
  { from: "Backend", to: "Preprocessing", label: "Diagnostics endpoint", path: "M375 320 H415 V421 H460" },
  { from: "Preprocessing", to: "RustFS", label: "Recording and output files", path: "M535 385 V318" },
  { from: "Preprocessing", to: "RabbitMQ", label: "Analysis tasks", path: "M615 421 H665" },
  { from: "RabbitMQ", to: "ML service", label: "Analysis tasks and completion events", path: "M810 421 H880 V267" },
  { from: "ML service", to: "Model DB", label: "Analysis results", path: "M880 195 V117" },
  { from: "Backend", to: "ML service", label: "Diagnostics endpoint", path: "M375 275 H405 V170 H780 V231 H805" },
  { from: "RabbitMQ", to: "Backend", label: "Analysis completion", path: "M738 457 V510 H295 V337" },
];

function connectionStatus(status: string | undefined): ConnectionStatus {
  if (status === "up" || status === "ok") return "connected";
  if (status === "down" || status === "error") return "disconnected";
  return "unknown";
}

function AdminSystemStatusPage() {
  const storage = useStorageUsage();
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    apiClient.get<SystemStatus>("/admin/system-status")
      .then(({ data }) => { if (active) { setSystemStatus(data); setError(false); } })
      .catch(() => { if (active) { setSystemStatus(null); setError(true); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [refresh]);

  const mlRabbit = [systemStatus?.ml.connections.rabbitmq_consumer?.status, systemStatus?.ml.connections.rabbitmq_publisher?.status].map(connectionStatus);
  const statuses: Record<string, ConnectionStatus> = {
    "Frontend-Backend": systemStatus ? "connected" : "unknown",
    "Backend-Auth DB": connectionStatus(systemStatus?.databases.auth_db?.status),
    "Backend-Medical DB": connectionStatus(systemStatus?.databases.medical_db?.status),
    "Backend-Audit DB": connectionStatus(systemStatus?.databases.audit_db?.status),
    "Backend-RustFS": connectionStatus(systemStatus?.backend.connections?.rustfs?.status),
    "RabbitMQ-Backend": connectionStatus(systemStatus?.backend.connections?.rabbitmq_consumer?.status),
    "Backend-Preprocessing": systemStatus ? (systemStatus.preprocessing.status === "down" ? "disconnected" : "connected") : "unknown",
    "Preprocessing-RustFS": connectionStatus(systemStatus?.preprocessing.connections.rustfs?.status),
    "Preprocessing-RabbitMQ": connectionStatus(systemStatus?.preprocessing.connections.rabbitmq?.status),
    "RabbitMQ-ML service": mlRabbit.includes("disconnected") ? "disconnected" : mlRabbit.every((status) => status === "connected") ? "connected" : "unknown",
    "ML service-Model DB": connectionStatus(systemStatus?.ml.connections.database?.status),
    "Backend-ML service": systemStatus ? (systemStatus.ml.status === "down" ? "disconnected" : "connected") : "unknown",
  };
  const connections: Connection[] = connectionLayout.map((connection) => ({ ...connection, status: statuses[`${connection.from}-${connection.to}`] ?? "unknown" }));
  const disconnected = connections.filter((connection) => connection.status === "disconnected");
  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>System Status</PageTitle>
      <Surface className="mb-4 border-white/80 bg-gradient-to-br from-white/65 to-[#e9f5f7]/55 shadow-[0_6px_18px_rgba(8,38,76,0.09)]">
        <SectionTitle>Storage usage</SectionTitle>
        {storage === "loading" ? <p className="rounded-xl border border-white/80 bg-white/40 px-4 py-5 text-sm text-[#52677b]" role="status">Loading storage usage...</p> : storage === "unavailable" ? <p className="rounded-xl border border-white/80 bg-white/40 px-4 py-5 text-sm text-[#52677b]" role="alert">Storage usage is unavailable.</p> : (
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="flex items-center gap-4 rounded-xl border border-white/80 bg-gradient-to-br from-white/75 to-[#d9f2f4]/65 p-4 shadow-[inset_0_1px_1px_rgba(255,255,255,0.85),0_3px_10px_rgba(8,38,76,0.06)]">
              
              <div className="min-w-0"><p className="text-xs font-semibold uppercase tracking-wide text-[#62798a]">RustFS bucket</p><p className="mt-1 break-all text-base font-bold text-[#102d58]">{storage.bucket}</p><p className="mt-1 text-xs text-[#62798a]">{storage.bucket_exists ? "Available" : "Not created yet"}</p></div>
            </div>
            <div className="rounded-xl border border-white/80 bg-white/45 p-4 shadow-[inset_0_1px_1px_rgba(255,255,255,0.85),0_3px_10px_rgba(8,38,76,0.06)]">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#62798a]">Used space</p>
              <p className="mt-3 font-heading text-2xl font-extrabold text-[#102d58]">{storage.bucket_exists ? formatBytes(storage.used_bytes) : "—"}</p>
            </div>
            <div className="rounded-xl border border-white/80 bg-white/45 p-4 shadow-[inset_0_1px_1px_rgba(255,255,255,0.85),0_3px_10px_rgba(8,38,76,0.06)]">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#62798a]">Objects</p>
              <p className="mt-3 font-heading text-2xl font-extrabold text-[#102d58]">{storage.bucket_exists ? storage.object_count.toLocaleString() : "—"}</p>
            </div>
          </div>
        )}
      </Surface>
      <Surface className="border-white/80 bg-gradient-to-br from-white/65 to-[#e9f5f7]/55 p-4 shadow-[0_6px_18px_rgba(8,38,76,0.09)] sm:p-6">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
            <SectionTitle>System connections</SectionTitle>
          <ButtonSecondary type="button" onClick={() => { setLoading(true); setRefresh((value) => value + 1); }} disabled={loading}>{loading ? "Checking..." : "Refresh"}</ButtonSecondary>
        </div>
        {error && <p role="alert" className="mb-4 rounded-lg border border-[#e6a5aa] bg-[#fff1f1] px-4 py-3 text-sm text-[#8d1d29]">System status is unavailable. Try refreshing.</p>}
        {!error && systemStatus && <p className="mb-4 text-sm text-[#52677b]" role="status">Overall status: <strong>{systemStatus.status === "ok" ? "Operational" : "Degraded"}</strong></p>}
        <div className="hidden overflow-x-auto rounded-xl border border-white/80 bg-white/35 sm:block">
          <svg className="block h-auto min-w-[850px] w-full" viewBox="0 0 980 550" role="img" aria-labelledby="system-diagram-title system-diagram-description">
            <title id="system-diagram-title">System connections diagram</title>
            <desc id="system-diagram-description">Connection statuses reported by system diagnostics. Connections without a dedicated check are unknown.</desc>
            <defs>
              <linearGradient id="node-glass" x1="0" y1="0" x2="1" y2="1"><stop stopColor="white" stopOpacity="0.8" /><stop offset="1" stopColor="#e7f5f6" stopOpacity="0.65" /></linearGradient>
              <linearGradient id="node-primary" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#f7ffff" stopOpacity="0.95" /><stop offset="1" stopColor="#c9edf0" stopOpacity="0.8" /></linearGradient>
              <filter id="node-shadow" x="-20%" y="-30%" width="140%" height="170%"><feDropShadow dx="0" dy="3" stdDeviation="5" floodColor="#123c51" floodOpacity="0.1" /></filter>
            </defs>
            {connections.map((connection) => (
              <path key={`${connection.from}-${connection.to}`} d={connection.path} fill="none" stroke={connection.status === "connected" ? "#47a984" : connection.status === "disconnected" ? "#b42332" : "#687783"} strokeWidth={connection.status === "disconnected" ? 5 : 2.5} strokeDasharray={connection.status === "connected" ? undefined : connection.status === "disconnected" ? "8 4" : "2 5"} strokeLinecap="round" strokeLinejoin="round">
                <title>{`${connection.from} to ${connection.to}: ${connection.label} — ${connection.status}`}</title>
              </path>
            ))}
            {services.map((service) => (
              <g key={service.name} transform={`translate(${service.x} ${service.y})`}>
                <rect width={service.width} height="72" rx="12" fill="#f2f9fa" />
                <rect width={service.width} height="72" rx="12" fill={service.kind === "app" ? "url(#node-primary)" : "url(#node-glass)"} stroke="white" strokeWidth="1.5" filter="url(#node-shadow)" />
                <text x="16" y="30" fill="#102d58" fontSize="15" fontWeight="700">{service.name}</text>
                <text x="16" y="51" fill="#62798a" fontSize="9" fontWeight="700" letterSpacing="0.07em">{service.description}</text>
              </g>
            ))}
          </svg>
        </div>
        <ul aria-label="System connections" className="space-y-2 sm:hidden">
          {connections.map((connection) => (
            <li className="rounded-lg border border-white/80 bg-white/45 p-3 text-sm text-[#173456]" key={`${connection.from}-${connection.to}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <strong>{connection.from} ? {connection.to}</strong>
                <span className={connection.status === "disconnected" ? "font-bold text-[#a51d2b]" : "font-semibold"}>{connection.status}</span>
              </div>
              <p className="mt-1 text-xs text-[#52677b]">{connection.label}</p>
            </li>
          ))}
        </ul>
        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs font-medium text-[#52677b]">
          <span className="flex items-center gap-2"><span className="h-0.5 w-6 rounded-full bg-[#47a984]" /> Connected</span>
          <span className="flex items-center gap-2 font-bold text-[#a51d2b]"><span className="w-6 border-t-4 border-dashed border-[#b42332]" /> Disconnected</span>
          <span className="flex items-center gap-2"><span className="w-6 border-t-2 border-dotted border-[#687783]" /> Unknown</span>
          <span className="sm:ml-auto">Unknown means no diagnostic result is available.</span>
        </div>
        {disconnected.length > 0 && (
          <div className="mt-4 rounded-lg border border-[#e6a5aa] bg-[#fff1f1] px-4 py-3 text-sm text-[#8d1d29]">
            <p className="font-bold">Disconnected connections ({disconnected.length})</p>
            <ul className="mt-1 list-inside list-disc">
              {disconnected.map((connection) => <li key={`${connection.from}-${connection.to}`}>{connection.from} → {connection.to} ({connection.label})</li>)}
            </ul>
          </div>
        )}
        <ul className="sr-only" aria-label="Connection statuses">
          {connections.map((connection) => <li key={`${connection.from}-${connection.to}`}>{connection.from} to {connection.to}, {connection.label}: {connection.status}.</li>)}
        </ul>
      </Surface>
    </div>
  );
}

export default AdminSystemStatusPage;
