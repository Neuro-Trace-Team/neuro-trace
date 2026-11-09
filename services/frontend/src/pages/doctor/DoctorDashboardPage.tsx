import { useNavigate } from "react-router-dom";
import DataTable from "../../components/DataTable";
import PageTitle from "../../components/PageTitle";
import SectionTitle from "../../components/SectionTitle";
import Surface from "../../components/Surface";
import { useAuth } from "../../context/useAuth";
import { formatDate } from "../../services/api";
import type { Examination } from "../../types/api.types";
export default function DoctorDashboardPage() {
    const { user } = useAuth(); const navigate = useNavigate();
    let history: Examination[] = [];
    try { history = JSON.parse(localStorage.getItem("neurotrace.recent." + (user?.id ?? "browser")) || "[]"); } catch { /* Storage unavailable. */ }
    const patients = [...new Map(history.map(x => [x.patient_id, x])).values()];
    return (
        <div className="mx-auto max-w-[1100px]">
            <PageTitle>Welcome back, {user?.firstName || "?"}</PageTitle>
            <div className="space-y-3">
                <Surface>
                    <SectionTitle>Recently Viewed Examinations</SectionTitle>
                    <DataTable columns={["Examination ID", "Date", "Patient ID"]} rows={history.map(x => [x.id, formatDate(x.examination_date ?? x.created_at), x.patient_id])} onRowClick={row => navigate(`/doctor/examinations/${row[0]}`)} sortable={false} selectable={false} showPagination={false} showToolbar={false} />
                </Surface>
                <Surface>
                    <SectionTitle>Recently Viewed Patients</SectionTitle>
                    <DataTable columns={["Patient ID"]} rows={patients.map(x => [x.patient_id])} onRowClick={row => navigate(`/doctor/examinations?patient_id=${encodeURIComponent(row[0])}`)} sortable={false} selectable={false} showPagination={false} showToolbar={false} />
                </Surface>
            </div>
        </div>
    );
}
