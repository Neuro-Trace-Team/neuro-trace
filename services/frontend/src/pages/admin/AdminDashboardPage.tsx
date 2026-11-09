import axios from "axios";
import { useEffect, useState } from "react";
import DataTable from "../../components/DataTable";
import PageTitle from "../../components/PageTitle";
import SectionTitle from "../../components/SectionTitle";
import Surface from "../../components/Surface";
import { apiClient, backendClient } from "../../services/apiClient";
import { formatDate } from "../../services/api";
import type { AuditLog, BackendReadiness, PaginatedResponse } from "../../types/api.types";
import AuditLogDetailsModal from "../../components/AuditLogDetailsModal";
export default function AdminDashboardPage() {
 const [logs,setLogs]=useState<AuditLog[]>([]); const [health,setHealth]=useState<BackendReadiness | null>(null); const [live,setLive]=useState("Checking"); const [error,setError]=useState(""); const [selected,setSelected]=useState<string | null>(null);
 useEffect(() => {
 apiClient.get<PaginatedResponse<AuditLog>>("/admin/audit-logs",{params:{page:1,page_size:10}}).then(({data})=>setLogs(data.items)).catch(()=>setError("Audit logs unavailable."));
 backendClient.get<{status:string}>("/health/live").then(({data})=>setLive(data.status)).catch(()=>setLive("Unavailable"));
 backendClient.get<BackendReadiness>("/health/ready").then(({data})=>setHealth(data)).catch(e=>{if(axios.isAxiosError<BackendReadiness>(e) && e.response?.data?.dependencies) setHealth(e.response.data);});
 },[]);
 return <div className="mx-auto max-w-[1100px]"><PageTitle>Administrator Dashboard</PageTitle><Surface className="mb-3"><SectionTitle>System Status</SectionTitle><p>Backend: {live}</p>{Object.entries(health?.dependencies ?? {}).map(([name,status])=><p key={name}>{name}: {status}</p>)}<p className="mt-2 text-sm">Other services: health information unavailable.</p></Surface><Surface><SectionTitle>Recent Audit Logs</SectionTitle>{error && <p>{error}</p>}<DataTable columns={["ID", "Date", "Event", "Resource"]} rows={logs.map(x=>[x.id,formatDate(x.created_at),x.event_code,[x.resource_type,x.resource_id].filter(Boolean).join(" ? ")])} sortable={false} selectable={false} showPagination={false} showToolbar={false} onRowClick={row=>setSelected(row[0])}/></Surface>{selected && <AuditLogDetailsModal logId={selected} onClose={()=>setSelected(null)}/>}</div>;
}
