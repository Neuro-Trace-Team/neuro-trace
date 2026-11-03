import { useParams } from "react-router-dom";
import DataTable from "../../components/DataTable";
import Icon from "../../components/Icon";
import { PageTitle, SectionTitle, SmallButton, Surface } from "../../components/PageUI";
import { examRows } from "../mockData";

const painValues = [6, 6, 6, 5, 7, 6, 4, 6, 7, 5];

function DoctorExaminationDetailsPage() {
  const { id = "81Jlyxsiw2" } = useParams();
  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Examination Results</PageTitle>
      <Surface className="mb-4 p-3">
        <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
          <div>
            <SectionTitle>Model Evaluation</SectionTitle>
            <p className="text-[11px]">Evaluation ID: <strong>{id}</strong></p>
            <p className="mt-1 text-[11px]">Patient ID: <strong>HJ53jbd7jwF</strong></p>
          </div>
          <SmallButton onClick={() => window.print()} type="button">
            <Icon className="h-4 w-4" name="download" />
            Export Report
          </SmallButton>
        </div>
        <div className="rounded-md border border-white/80 bg-white/50 p-2.5 shadow-sm">
          <h3 className="mb-1 text-[17px] font-semibold">Detected Pain Levels</h3>
          <div className="grid gap-4 md:grid-cols-[minmax(180px,0.58fr)_1fr]">
            <div className="max-h-[170px] space-y-1 overflow-y-auto pr-1">
              {painValues.map((value, index) => (
                <div className="flex h-[22px] items-center justify-between rounded-full bg-[#dedfe0] px-2 text-[11px]" key={index}>
                  <span>00:00:09:124</span><strong>{value}</strong>
                </div>
              ))}
            </div>
            <div className="pt-4">
              <div className="relative h-5 rounded-full bg-gradient-to-r from-[#83e3ce] via-[#f2d88a] to-[#b53c3c]">
                <span className="absolute left-[60%] top-1/2 h-4 w-4 -translate-y-1/2 rounded-full border-2 border-white bg-white shadow" />
              </div>
              <div className="mt-1 flex justify-between text-[11px]">
                {Array.from({ length: 11 }, (_, index) => (
                  <span className={index === 6 ? "font-bold text-[#00a9c4]" : ""} key={index}>{index}</span>
                ))}
              </div>
              <p className="mt-4 text-right text-[16px]">Certainty: <strong>70%</strong></p>
            </div>
          </div>
        </div>
        <p className="mt-4 text-[10px] font-semibold">Notice</p>
        <p className="text-[10px]">Remember that the model's result is only a help and does not constitute a substitution to a professional doctor's opinion.</p>
      </Surface>

      <Surface className="p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SectionTitle>Patient’s Examination History</SectionTitle>
          <SmallButton onClick={() => window.print()} type="button">
            <Icon className="h-4 w-4" name="download" />
            Export Full History
          </SmallButton>
        </div>
        <DataTable columns={["Examination ID", "Date"]} rows={examRows.map(([examId, date]) => [examId, date])} totalCount={112} />
      </Surface>
    </div>
  );
}

export default DoctorExaminationDetailsPage;
