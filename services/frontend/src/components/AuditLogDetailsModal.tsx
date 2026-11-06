import { useEffect, useState } from "react";
import Modal from "./Modal";
import { apiClient, getApiErrorMessage } from "../services/apiClient";
import { formatDate } from "../services/api";
import type { AuditLog } from "../types/api.types";

function Detail({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="grid gap-1 border-b border-[#e1e8eb] py-3 last:border-0 sm:grid-cols-[150px_minmax(0,1fr)] sm:items-start sm:gap-4">
      <dt className="text-xs font-bold uppercase tracking-wide text-[#52677b]">{label}</dt>
      <dd className="break-all text-sm text-[#102d58]">{value || "—"}</dd>
    </div>
  );
}

export default function AuditLogDetailsModal({
  logId,
  onClose,
}: {
  logId: string;
  onClose: () => void;
}) {
  const [log, setLog] = useState<AuditLog | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    apiClient
      .get<AuditLog>(`/admin/audit-logs/${logId}`)
      .then(({ data }) => {
        if (active) setLog(data);
      })
      .catch((loadError: unknown) => {
        if (active) setError(getApiErrorMessage(loadError, "Failed to load log details."));
      });
    return () => {
      active = false;
    };
  }, [logId]);

  return (
    <Modal
      className="max-w-[680px]"
      description="Audit log information fetched from the backend."
      onClose={onClose}
      title="Event details"
    >
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{error}</p>}
      {!log && !error && (
        <p className="py-8 text-center text-sm text-[#52677b]" role="status">
          Loading event details...
        </p>
      )}
      {log && (
        <dl className="divide-y divide-[#e1e8eb]">
          <Detail label="Event" value={log.event_code} />
          <Detail label="Timestamp" value={formatDate(log.created_at)} />
          <Detail label="Log ID" value={log.id} />
          <Detail label="User" value={log.user_id} />
          <Detail label="Resource type" value={log.resource_type} />
          <Detail label="Resource ID" value={log.resource_id} />
          <Detail label="IP address" value={log.ip_address} />
          <Detail label="Request ID" value={log.request_id} />
          <div className="py-3">
            <dt className="mb-2 text-xs font-bold uppercase tracking-wide text-[#52677b]">Metadata</dt>
            <dd>
              {log.metadata ? (
                <pre className="max-h-64 overflow-auto rounded-lg border border-[#dce5e9] bg-white/80 p-3 text-xs leading-5 text-[#102d58]">
                  {JSON.stringify(log.metadata, null, 2)}
                </pre>
              ) : (
                <p className="text-sm text-[#102d58]">No additional metadata.</p>
              )}
            </dd>
          </div>
        </dl>
      )}
    </Modal>
  );
}
