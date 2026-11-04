import { useEffect, useState } from "react";
import DataTable from "../../components/DataTable";
import { PageTitle, SectionTitle, Surface } from "../../components/PageUI";
import { useAuth } from "../../context/useAuth";
import { apiClient, getApiErrorMessage } from "../../services/apiClient";
import { formatDate } from "../../services/api";
import type { AdminDashboard, AuditLog, PaginatedResponse } from "../../types/api.types";
import AuditLogDetailsModal from "../../components/AuditLogDetailsModal";
import { useToast } from "../../context/useToast";

function AdminDashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<AdminDashboard | null>(null);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState("");
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const { showToast } = useToast();

  useEffect(() => {
    Promise.all([
      apiClient.get<AdminDashboard>("/admin/dashboard", { params: { period: "30d" } }),
      apiClient.get<PaginatedResponse<AuditLog>>("/admin/audit-logs", {
        params: { page: 1, page_size: 10 },
      }),
    ])
      .then(([dashboard, auditLogs]) => {
        setStats(dashboard.data);
        setLogs(auditLogs.data.items);
      })
      .catch((loadError: unknown) => {
        const message = getApiErrorMessage(loadError, "Could not load the dashboard.");
        setError(message);
        showToast(message, "error");
      });
  }, [showToast]);

  const statCards = stats
    ? [
      { label: "Active users (30 days)", value: stats.active_users },
      { label: "Failed logins (30 days)", value: stats.failed_logins },
      { label: "Registered users", value: stats.total_users },
      { label: "Examinations (30 days)", value: stats.examinations_created },
    ]
    : [];
  const activityRows = logs.map((log) => [
    formatDate(log.created_at),
    log.event_code,
    [log.resource_type, log.resource_id].filter(Boolean).join(" · ") || "—",
  ]);

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Welcome back, {user?.firstName || "—"}</PageTitle>
      <Surface className="mb-3 px-5 py-3">
        <SectionTitle>System Status</SectionTitle>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {statCards.map((stat) => (
            <div
              key={stat.label}
              className="flex aspect-square w-full flex-col justify-between rounded-2xl border border-white/60 bg-white/40 p-5 shadow-[0_8px_30px_rgb(0,0,0,0.06)] backdrop-blur-md"
            >
              <span className="text-xs font-medium leading-relaxed text-[#0d233a]/80 sm:text-sm">
                {stat.label}
              </span>
              <div className="flex flex-1 items-center justify-center">
                <strong className="text-center font-heading font-extrabold tracking-tight text-[#0d233a] sm:text-4xl md:text-7xl">
                  {stat.value ?? "—"}
                </strong>
              </div>
            </div>
          ))}
          {!stats && !error && <p className="col-span-full text-sm text-[#52677b]">Loading statistics...</p>}
        </div>
      </Surface>
      <Surface className="px-4 py-3">
        <SectionTitle>Recent App Activity</SectionTitle>
        <DataTable
          columns={["Date", "Event", "Resource"]}
          rows={activityRows}
          sortable={false}
          selectable={false}
          showPagination={false}
          showToolbar={false}
          onRowClick={(_row, rowIndex) => setSelectedLogId(logs[rowIndex]?.id ?? null)} />
      </Surface>
      {selectedLogId && (
        <AuditLogDetailsModal
          logId={selectedLogId}
          onClose={() => setSelectedLogId(null)}
        />
      )}
    </div>
  );
}

export default AdminDashboardPage;
