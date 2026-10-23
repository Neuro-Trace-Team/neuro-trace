import { useNavigate } from "react-router-dom";
import DataTable from "../../components/DataTable";
import { PageTitle, Surface } from "../../components/PageUI";
import { examRows } from "../mockData";

function DoctorExaminationsPage() {
  const navigate = useNavigate();
  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Browse Examinations</PageTitle>
      <Surface>
        <DataTable
          columns={["Examination ID", "Date", "Patient ID"]}
          onRowClick={() => navigate("/doctor/examinations/BE9d7nB72na")}
          rows={examRows}
          searchPlaceholder="Search examinations"
          toolbarEnd={
            <label className="flex min-h-8 items-center gap-2 rounded-md border border-white/90 bg-white/70 px-2.5 text-[12px] font-semibold">
              <input className="h-3.5 w-3.5 accent-[#00a9c4]" type="checkbox" />
              Show my examinations only
            </label>
          }
        />
      </Surface>
    </div>
  );
}

export default DoctorExaminationsPage;
