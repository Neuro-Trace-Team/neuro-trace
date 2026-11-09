import { useEffect, useState } from "react";
import AuditLogDetailsModal from "../../components/AuditLogDetailsModal";
import DataTable from "../../components/DataTable";
import PageTitle from "../../components/PageTitle";
import SectionTitle from "../../components/SectionTitle";
import Surface from "../../components/Surface";
import { apiClient } from "../../services/apiClient";
import { formatDate } from "../../services/api";
import type { AuditLog, PaginatedResponse } from "../../types/api.types";

type CountState = number | "loading" | "unavailable";

function ActivityCard({ label, value }: { label: string; value: CountState }) {
  return (
    <div className="flex aspect-square min-w-0 flex-col rounded-xl border border-white/80 bg-gradient-to-br from-white/65 to-[#e9f5f7]/45 p-4 shadow-[inset_0_1px_1px_rgba(255,255,255,0.85),0_3px_10px_rgba(8,38,76,0.08)]">
      <h3 className="text-sm font-semibold leading-5 text-[#173456]">{label}</h3>
      <div className="flex flex-1 items-center justify-center text-center font-heading text-5xl font-extrabold leading-none text-[#06234e] sm:text-6xl">
        {typeof value === "number" ? value.toLocaleString() : value === "loading" ? <span className="text-sm font-semibold text-[#52677b]">Loading...</span> : <span aria-label="Unavailable">—</span>}
      </div>
    </div>
  );
}

export default function AdminDashboardPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [failedLogins, setFailedLogins] = useState<CountState>("loading");
  const [uploadedExaminations, setUploadedExaminations] = useState<CountState>("loading");

  useEffect(() => {
    let active = true;
    const now = Date.now();
    const params = { page: 1, page_size: 1, created_at_from: new Date(now - 24 * 60 * 60 * 1000).toISOString(), created_at_to: new Date(now).toISOString() };
    apiClient.get<PaginatedResponse<AuditLog>>("/admin/audit-logs", { params: { page: 1, page_size: 10 } })
      .then(({ data }) => { if (active) setLogs(data.items); })
      .catch(() => { if (active) setError("Audit logs unavailable."); });
    apiClient.get<PaginatedResponse<AuditLog>>("/admin/audit-logs", { params: { ...params, event_code: "FAILED_LOGIN_ATTEMPT" } })
      .then(({ data }) => { if (active) setFailedLogins(data.total); })
      .catch(() => { if (active) setFailedLogins("unavailable"); });
    apiClient.get<PaginatedResponse<AuditLog>>("/admin/audit-logs", { params: { ...params, event_code: "EXAMINATION_UPLOADED" } })
      .then(({ data }) => { if (active) setUploadedExaminations(data.total); })
      .catch(() => { if (active) setUploadedExaminations("unavailable"); });
    return () => { active = false; };
  }, []);

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Administrator Dashboard</PageTitle>
      <Surface className="mb-3">
        <SectionTitle>App Activity</SectionTitle>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
          <ActivityCard label="Active users in the last 24h" value="unavailable" />
          <ActivityCard label="Failed login attempts in the last 24h" value={failedLogins} />
          <ActivityCard label="Storage usage" value="unavailable" />
          <ActivityCard label="Examinations uploaded in the last 24h" value={uploadedExaminations} />
        </div>
      </Surface>
      <Surface>
        <SectionTitle>Recent Audit Logs</SectionTitle>
        {error && <p>{error}</p>}
        <DataTable columns={["ID", "Date", "Event", "Resource"]} rows={logs.map((log) => [log.id, formatDate(log.created_at), log.event_code, [log.resource_type, log.resource_id].filter(Boolean).join(" · ")])} sortable={false} selectable={false} showPagination={false} showToolbar={false} onRowClick={(row) => setSelected(row[0])} />
      </Surface>
      {selected && <AuditLogDetailsModal logId={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
