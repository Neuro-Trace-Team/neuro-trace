import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable from "../../components/DataTable";
import PageTitle from "../../components/PageTitle";
import SectionTitle from "../../components/SectionTitle";
import Surface from "../../components/Surface";
import { useAuth } from "../../context/useAuth";
import { formatDate } from "../../services/api";
import { apiClient, getApiErrorMessage } from "../../services/apiClient";
import type { Examination, Patient } from "../../types/api.types";

export default function DoctorDashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [history, setHistory] = useState<Examination[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [examinationsError, setExaminationsError] = useState("");
  const [patientsError, setPatientsError] = useState("");
  const [examinationsLoading, setExaminationsLoading] = useState(true);
  const [patientsLoading, setPatientsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    apiClient.get<Examination[]>("/me/recent/examinations")
      .then(({ data }) => { if (active) setHistory(data); })
      .catch((error: unknown) => { if (active) setExaminationsError(getApiErrorMessage(error, "Could not load recent examinations.")); })
      .finally(() => { if (active) setExaminationsLoading(false); });
    apiClient.get<Patient[]>("/me/recent/patients")
      .then(({ data }) => { if (active) setPatients(data); })
      .catch((error: unknown) => { if (active) setPatientsError(getApiErrorMessage(error, "Could not load recent patients.")); })
      .finally(() => { if (active) setPatientsLoading(false); });
    return () => { active = false; };
  }, []);

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Welcome back, {user?.firstName || "?"}</PageTitle>
      <div className="space-y-3">
        <Surface>
          <SectionTitle>Recently Viewed Examinations</SectionTitle>
          {examinationsLoading ? <p role="status">Loading recent examinations...</p> : examinationsError ? <p role="alert">{examinationsError}</p> : (
            <DataTable columns={["Examination ID", "Date", "Patient ID"]} rows={history.map((item) => [item.id, formatDate(item.examination_date ?? item.created_at), item.patient_id])} onRowClick={(row) => navigate(`/doctor/examinations/${row[0]}`)} sortable={false} selectable={false} showPagination={false} showToolbar={false} />
          )}
        </Surface>
        <Surface>
          <SectionTitle>Recently Viewed Patients</SectionTitle>
          {patientsLoading ? <p role="status">Loading recent patients...</p> : patientsError ? <p role="alert">{patientsError}</p> : (
            <DataTable columns={["Patient ID"]} rows={patients.map((patient) => [patient.id])} onRowClick={(row) => navigate(`/doctor/examinations?patient_id=${encodeURIComponent(row[0])}`)} sortable={false} selectable={false} showPagination={false} showToolbar={false} />
          )}
        </Surface>
      </div>
    </div>
  );
}
