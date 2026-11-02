import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import DataTable from "../../components/DataTable";
import ButtonSecondary from "../../components/ButtonSecondary";
import { useToast } from "../../context/useToast";
import { PageTitle, SectionTitle, Surface } from "../../components/PageUI";
import { apiClient, getApiErrorMessage } from "../../services/apiClient";
import { formatDate } from "../../services/api";
import type {
  Examination,
  ExaminationResult,
  PaginatedResponse,
  PainAssessment,
} from "../../types/api.types";

type PatientExamination = {
  id: string;
  examination_date: string | null;
  created_at: string;
};

function DoctorExaminationDetailsPage() {
  const { showToast } = useToast();
  const { id } = useParams();
  const navigate = useNavigate();
  const [examination, setExamination] = useState<Examination | null>(null);
  const [results, setResults] = useState<ExaminationResult[]>([]);
  const [resultsTotal, setResultsTotal] = useState(0);
  const [resultsPage, setResultsPage] = useState(1);
  const [assessments, setAssessments] = useState<PainAssessment[]>([]);
  const [assessmentsTotal, setAssessmentsTotal] = useState(0);
  const [assessmentsPage, setAssessmentsPage] = useState(1);
  const [history, setHistory] = useState<PatientExamination[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    apiClient
      .get<Examination>(`/examinations/${id}`)
      .then(({ data }) => {
        setExamination(data);
      })
      .catch((loadError: unknown) => {
        const message = getApiErrorMessage(loadError, "Could not load examination details.");
        setError(message);
        showToast(message, "error");
      });
  }, [id, showToast]);

  useEffect(() => {
    if (!id) return;
    apiClient
      .get<PaginatedResponse<ExaminationResult>>(`/examinations/${id}/results`, {
        params: { page: resultsPage, page_size: 20 },
      })
      .then(({ data }) => {
        setResults(data.items);
        setResultsTotal(data.total);
      })
      .catch((loadError: unknown) => {
        showToast(getApiErrorMessage(loadError, "Could not load model results."), "error");
      });
  }, [id, resultsPage, showToast]);

  useEffect(() => {
    if (!id) return;
    apiClient
      .get<PaginatedResponse<PainAssessment>>(`/examinations/${id}/pain-assessments`, {
        params: { page: assessmentsPage, page_size: 20 },
      })
      .then(({ data }) => {
        setAssessments(data.items);
        setAssessmentsTotal(data.total);
      })
      .catch((loadError: unknown) => {
        showToast(getApiErrorMessage(loadError, "Could not load pain assessments."), "error");
      });
  }, [assessmentsPage, id, showToast]);

  useEffect(() => {
    if (!examination) return;
    apiClient
      .get<PaginatedResponse<PatientExamination>>(
        `/patients/${examination.patient_id}/examinations`,
        { params: { page: historyPage, page_size: 20 } },
      )
      .then(({ data }) => {
        setHistory(data.items);
        setHistoryTotal(data.total);
      })
      .catch((loadError: unknown) => {
        showToast(getApiErrorMessage(loadError, "Could not load examination history."), "error");
      });
  }, [examination, historyPage, showToast]);

  const downloadReport = async (examinationIds: string[]) => {
    try {
      const { data } = await apiClient.post<Blob>(
        "/examinations/bulk-report",
        { examination_ids: examinationIds },
        { responseType: "blob" },
      );
      const url = URL.createObjectURL(data);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "neurotrace-medical-report.pdf";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (downloadError) {
      showToast(getApiErrorMessage(downloadError, "Could not export the report."), "error");
    }
  };

  const resultRows = results.map(({ analysis, result }) => [
    analysis.model_name,
    result.pain_level === null ? "—" : String(result.pain_level),
    result.confidence === null ? "—" : `${Math.round(Number(result.confidence) * 100)}%`,
    analysis.status,
    formatDate(analysis.created_at),
  ]);
  const historyRows = history.map((item) => [
    item.id,
    formatDate(item.examination_date ?? item.created_at),
  ]);
  const assessmentRows = assessments.map((assessment) => [
    String(assessment.pain_level),
    assessment.scale,
    assessment.notes ?? "—",
    formatDate(assessment.assessed_at),
  ]);

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Examination Results</PageTitle>
      {!examination && !error && <p className="mb-3 text-sm text-[#52677b]">Loading examination...</p>}
      {examination && (
        <>
          <Surface className="mb-4 p-3">
            <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
              <div>
                <SectionTitle>Examination</SectionTitle>
                <p className="text-[11px]">Examination ID: <strong>{examination.id}</strong></p>
                <p className="text-[11px]">Patient ID: <strong>{examination.patient_id}</strong></p>
                <p className="text-[11px]">File: <strong>{examination.original_filename}</strong> · {examination.processing_status}</p>
              </div>
              <ButtonSecondary icon="download" onClick={() => void downloadReport([examination.id])} type="button">
                Export Report
              </ButtonSecondary>
            </div>
            <SectionTitle>Model Evaluations</SectionTitle>
            <DataTable
              columns={["Model", "Pain level", "Confidence", "Status", "Created"]}
              itemLabel="analysis result"
              itemLabelPlural="analysis results"
              currentPage={resultsPage}
              onPageChange={setResultsPage}
              pageSize={20}
              rows={resultRows}
              totalCount={resultsTotal}
              selectable={false}
            />
            {results.length === 0 && <p className="mt-2 text-sm text-[#52677b]">No model results are available for this examination.</p>}
          </Surface>

          <Surface className="mb-4 p-3">
            <SectionTitle>Doctor Pain Assessments</SectionTitle>
            <DataTable
              columns={["Pain level", "Scale", "Notes", "Assessed at"]}
              itemLabel="pain assessment"
              itemLabelPlural="pain assessments"
              currentPage={assessmentsPage}
              onPageChange={setAssessmentsPage}
              pageSize={20}
              rows={assessmentRows}
              totalCount={assessmentsTotal}
              selectable={false}
            />
            {assessments.length === 0 && <p className="mt-2 text-sm text-[#52677b]">No pain assessments are available.</p>}
          </Surface>

          <Surface className="p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <SectionTitle>Patient’s Examination History</SectionTitle>
              <ButtonSecondary icon="download" onClick={() => void downloadReport(history.map((item) => item.id))} type="button" disabled={!history.length}>
                Export This Page
              </ButtonSecondary>
            </div>
            <DataTable
              columns={["Examination ID", "Date"]}
              itemLabel="examination"
              itemLabelPlural="examinations"
              currentPage={historyPage}
              onPageChange={setHistoryPage}
              pageSize={20}
              onRowClick={(row) => navigate(`/doctor/examinations/${row[0]}`)}
              rows={historyRows}
              totalCount={historyTotal}
              selectable={false}
            />
          </Surface>
        </>
      )}
    </div>
  );
}

export default DoctorExaminationDetailsPage;
