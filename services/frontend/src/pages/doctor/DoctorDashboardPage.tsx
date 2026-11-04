import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable from "../../components/DataTable";
import { PageTitle, SectionTitle, Surface } from "../../components/PageUI";
import { useAuth } from "../../context/useAuth";
import { apiClient, getApiErrorMessage } from "../../services/apiClient";
import { formatDate } from "../../services/api";
import type { DoctorDashboard, PaginatedResponse, Patient, PatientStatistics } from "../../types/api.types";
import { useToast } from "../../context/useToast";

function DoctorDashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<DoctorDashboard | null>(null);
  const [patientRows, setPatientRows] = useState<string[][]>([]);
  const { showToast } = useToast();

  useEffect(() => {
    Promise.all([
      apiClient.get<DoctorDashboard>("/dashboard/stats"),
      apiClient.get<PaginatedResponse<Patient>>("/patients", {
        params: { page: 1, page_size: 10 },
      }),
    ])
      .then(async ([dashboardResponse, patientsResponse]) => {
        setDashboard(dashboardResponse.data);
        const stats = await Promise.all(
          patientsResponse.data.items.map((patient) =>
            apiClient.get<PatientStatistics>(`/patients/${patient.id}/stats`),
          ),
        );
        setPatientRows(
          stats.map(({ data }) => [
            data.patient_id,
            String(data.examination_count),
            formatDate(data.first_examination_at),
            formatDate(data.last_examination_at),
          ]),
        );
      })
      .catch((loadError: unknown) => {
        showToast(getApiErrorMessage(loadError, "Could not load dashboard data."), "error");
      });
  }, [showToast]);

  const examinationRows = (dashboard?.recent_examinations ?? []).map((item) => [
    item.id,
    formatDate(item.created_at),
    item.patient_id,
  ]);

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Welcome back, {user?.firstName || "—"}</PageTitle>
      <div className="space-y-3">
        <Surface>
          <SectionTitle>Recently Viewed Examinations</SectionTitle>
          <DataTable
            columns={["Examination ID", "Date", "Patient ID"]}
            onRowClick={(row) => navigate(`/doctor/examinations/${row[0]}`)}
            rows={examinationRows}
            sortable={false}
            selectable={false}
            showPagination={false}
            showToolbar={false} />
        </Surface>
        <Surface>
          <SectionTitle>Recently Viewed Patients</SectionTitle>
          <DataTable
            columns={["Patient ID", "Number of Examinations", "First Examination", "Latest Examination"]}
            rows={patientRows}
            sortable={false}
            selectable={false}
            showPagination={false}
            showToolbar={false} />
        </Surface>
      </div>
    </div>
  );
}

export default DoctorDashboardPage;
