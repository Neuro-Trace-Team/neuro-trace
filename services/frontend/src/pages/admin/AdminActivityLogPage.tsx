import { useEffect, useState } from "react";
import AuditLogDetailsModal from "../../components/AuditLogDetailsModal";
import DataTable from "../../components/DataTable";
import InputSection from "../../components/InputSection";
import PageTitle from "../../components/PageTitle";
import Surface from "../../components/Surface";
import { apiClient, getApiErrorMessage } from "../../services/apiClient";
import { formatDate } from "../../services/api";
import type { AuditLog, PaginatedResponse } from "../../types/api.types";
import { useToast } from "../../context/useToast";

type LogFilters = {
  event_code: string;
  user_id: string;
  date_from: string;
  date_to: string;
};

const emptyFilters: LogFilters = {
  event_code: "",
  user_id: "",
  date_from: "",
  date_to: "",
};
type SortField = "created_at" | "event_code";
type SortOrder = "asc" | "desc";

function toApiDate(value: string) {
  return value ? new Date(value).toISOString() : undefined;
}

function AdminActivityLogPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const [filters, setFilters] = useState(emptyFilters);
  const [draftFilters, setDraftFilters] = useState(emptyFilters);
  const [sortBy, setSortBy] = useState<SortField>("created_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const { showToast } = useToast();

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim().toUpperCase()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    const params = {
      page,
      page_size: 20,
      event_code: debouncedSearch || filters.event_code || undefined,
      user_id: filters.user_id || undefined,
      date_from: toApiDate(filters.date_from),
      date_to: toApiDate(filters.date_to),
      sort_by: sortBy,
      sort_order: sortOrder,
    };
    void apiClient
      .get<PaginatedResponse<AuditLog>>("/admin/audit-logs", {
        params,
      })
      .then(({ data }) => {
        setLogs(data.items);
        setTotal(data.total);
      })
      .catch((loadError: unknown) => {
        showToast(getApiErrorMessage(loadError, "Could not load the activity log."), "error");
      })
      .finally(() => setIsLoading(false));
  }, [debouncedSearch, filters, page, showToast, sortBy, sortOrder]);

  const updateDraft = <K extends keyof LogFilters>(key: K, value: LogFilters[K]) => {
    setDraftFilters((current) => ({ ...current, [key]: value }));
  };
  const filtersActive = Object.entries(filters).some(
    ([key, value]) => value !== emptyFilters[key as keyof LogFilters],
  );

  const rows = logs.map((log) => [
    formatDate(log.created_at),
    log.event_code,
    [log.resource_type, log.resource_id, log.user_id].filter(Boolean).join(" · ") || "—",
  ]);

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Audit Log</PageTitle>
      <Surface className="p-3">
        <DataTable
          columns={["Date", "Event", "Resource / User"]}
          sortBy={sortBy}
          sortOrder={sortOrder}
          sortableColumns={{ Date: "created_at", Event: "event_code" }}
          onSortChange={(nextSortBy, nextSortOrder) => {
            setIsLoading(true);
            setPage(1);
            setSortBy(nextSortBy as SortField);
            setSortOrder(nextSortOrder);
          }}
          itemLabel="log"
          itemLabelPlural="logs"
          currentPage={page}
          onPageChange={(nextPage) => {
            setIsLoading(true);
            setPage(nextPage);
          }}
          pageSize={20}
          rows={rows}
          rowIds={logs.map((log) => log.id)}
          totalCount={total}
          searchPlaceholder="Search event code (exact)"
          searchValue={search}
          onSearchChange={(nextSearch) => {
            setSearch(nextSearch);
            setIsLoading(true);
            setPage(1);
          }}
          showFilters
          filtersActive={filtersActive}
          filterTitle="Filter activity logs"
          onApplyFilters={() => {
            setIsLoading(true);
            setPage(1);
            setFilters(draftFilters);
          }}
          onClearFilters={() => {
            setDraftFilters(emptyFilters);
            setFilters(emptyFilters);
            setPage(1);
            setIsLoading(true);
          }}
          filterContent={(
            <div className="grid gap-4 sm:grid-cols-2">
              <InputSection label="Event code" maxLength={100} name="event-code-filter" onChange={(event) => updateDraft("event_code", event.target.value)} placeholder="e.g. LOGIN" value={draftFilters.event_code} />
              <InputSection label="User ID" name="user-id-filter" onChange={(event) => updateDraft("user_id", event.target.value)} placeholder="UUID" value={draftFilters.user_id} />
              <InputSection label="From" name="log-date-from" onChange={(event) => updateDraft("date_from", event.target.value)} type="datetime-local" value={draftFilters.date_from} />
              <InputSection label="To" name="log-date-to" onChange={(event) => updateDraft("date_to", event.target.value)} type="datetime-local" value={draftFilters.date_to} />
            </div>
          )}
          onRowClick={(_row, rowIndex) => setSelectedLogId(logs[rowIndex]?.id ?? null)}
        />
        {isLoading && <p className="mt-3 text-sm text-[#52677b]">Loading activity...</p>}
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

export default AdminActivityLogPage;
