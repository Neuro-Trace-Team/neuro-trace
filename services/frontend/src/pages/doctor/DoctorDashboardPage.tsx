import { useNavigate } from "react-router-dom";
import DataTable from "../../components/DataTable";
import { PageTitle, SectionTitle, Surface } from "../../components/PageUI";
import { useAuth } from "../../context/AuthContext";
import { examRows, patientRows } from "../mockData";

function DoctorDashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const firstName = user?.firstName || "Alice";

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Welcome back, {firstName}</PageTitle>
      <div className="space-y-3">
        <Surface>
          <SectionTitle>Recently Viewed Examinations</SectionTitle>
          <DataTable columns={["Examination ID", "Date", "Patient ID"]} onRowClick={() => navigate("/doctor/examinations/BE9d7nB72na")} rows={examRows.slice(0, 9)} selectable={false} showPagination={false} showToolbar={false} />
        </Surface>
        <Surface>
          <SectionTitle>Recently Viewed Patients</SectionTitle>
          <DataTable columns={["Patient ID", "Number of Examinations", "First Examination", "Latest Examination"]} rows={patientRows.slice(0, 10)} selectable={false} showPagination={false} showToolbar={false} />
        </Surface>
      </div>
    </div>
  );
}

export default DoctorDashboardPage;
