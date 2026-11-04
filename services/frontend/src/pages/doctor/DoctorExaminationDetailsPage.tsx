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

type DetectedPainLevel = {
  timestamp: number;
  painLevel: number;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getDetectedPainLevels(result: ExaminationResult | undefined): DetectedPainLevel[] {
  const detections = result?.result.result?.detected_pain_levels;
  if (!Array.isArray(detections)) return [];

  return detections
    .flatMap((detection) => {
      if (!isRecord(detection)) return [];
      const timestamp = Number(detection.timestamp);
      const painLevel = Number(detection.pain_level);
      if (!Number.isFinite(timestamp) || timestamp < 0 || !Number.isFinite(painLevel) || painLevel < 0 || painLevel > 10) {
        return [];
      }
      return [{ timestamp, painLevel }];
    })
    .sort((first, second) => first.timestamp - second.timestamp);
}

function formatTimestamp(seconds: number): string {
  const totalMilliseconds = Math.round(seconds * 1000);
  const hours = Math.floor(totalMilliseconds / 3_600_000);
  const minutes = Math.floor((totalMilliseconds % 3_600_000) / 60_000);
  const remainingSeconds = Math.floor((totalMilliseconds % 60_000) / 1000);
  const milliseconds = totalMilliseconds % 1000;
  return [hours, minutes, remainingSeconds].map((part) => String(part).padStart(2, "0")).join(":")
    + `:${String(milliseconds).padStart(3, "0")}`;
}

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
  const [isExportingHistory, setIsExportingHistory] = useState(false);
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

  const downloadFullHistory = async () => {
    if (!examination || !historyTotal || isExportingHistory) return;
    setIsExportingHistory(true);
    try {
      const pageSize = 100;
      const pageCount = Math.ceil(historyTotal / pageSize);
      const historyPages = await Promise.all(
        Array.from({ length: pageCount }, (_, index) => index + 1).map((page) =>
          apiClient.get<PaginatedResponse<PatientExamination>>(
            `/patients/${examination.patient_id}/examinations`,
            { params: { page, page_size: pageSize } },
          ),
        ),
      );
      await downloadReport([
        ...new Set(historyPages.flatMap(({ data }) => data.items.map((item) => item.id))),
      ]);
    } catch (exportError) {
      showToast(getApiErrorMessage(exportError, "Could not load the complete examination history."), "error");
    } finally {
      setIsExportingHistory(false);
    }
  };

  const selectedResult = results.find(({ analysis }) => analysis.status === "COMPLETED") ?? results[0];
  const detectedPainLevels = getDetectedPainLevels(selectedResult);
  const painLevel = selectedResult?.result.pain_level === null || selectedResult?.result.pain_level === undefined
    ? null
    : Number(selectedResult.result.pain_level);
  const confidence = selectedResult?.result.confidence === null || selectedResult?.result.confidence === undefined
    ? null
    : Number(selectedResult.result.confidence);
  const validPainLevel = painLevel !== null && Number.isFinite(painLevel) && painLevel >= 0 && painLevel <= 10
    ? painLevel
    : null;
  const validConfidence = confidence !== null && Number.isFinite(confidence)
    ? Math.max(0, Math.min(1, confidence))
    : null;
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
          <Surface className="mb-4 p-3 sm:p-4">
            <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
              <div>
                <SectionTitle>Model Evaluation</SectionTitle>
                <p className="text-xs text-[#334b63]">Evaluation ID: <strong className="break-all text-[#102d58]">{selectedResult?.analysis.id ?? "—"}</strong></p>
                <p className="mt-1 text-xs text-[#334b63]">Patient ID: <strong className="break-all text-[#102d58]">{examination.patient_id}</strong></p>
                <p className="mt-1 text-xs text-[#52677b]">
                  Examination: {examination.original_filename} · {examination.processing_status}
                </p>
              </div>
              <ButtonSecondary icon="download" onClick={() => void downloadReport([examination.id])} type="button">
                Export Report
              </ButtonSecondary>
            </div>
            <div className="rounded-lg border border-[#dce5e9] bg-white/75 p-3 shadow-[0_2px_6px_rgba(8,38,76,0.10)] sm:p-4">
              <h3 className="mb-3 text-base font-semibold text-[#08264c]">Detected Pain Levels</h3>
              <div className="grid gap-4 md:grid-cols-[minmax(190px,0.8fr)_minmax(0,1.8fr)] md:items-center">
                <div aria-label="Detected pain levels by timestamp" className="max-h-36 space-y-1 overflow-y-auto pr-1">
                  {detectedPainLevels.length ? detectedPainLevels.map((detection, index) => (
                    <div className="flex items-center justify-between gap-3 rounded-full bg-[#edf1f3] px-2.5 py-1 text-xs text-[#334b63]" key={`${detection.timestamp}-${index}`}>
                      <span className="font-mono">{formatTimestamp(detection.timestamp)}</span>
                      <strong className="text-[#102d58]">{detection.painLevel}</strong>
                    </div>
                  )) : (
                    <p className="py-2 text-xs text-[#718096]">No timestamped pain detections are available.</p>
                  )}
                </div>
                <div>
                  <div
                    aria-label={validPainLevel === null ? "Pain score unavailable" : `Pain score ${validPainLevel} out of 10`}
                    className="relative h-5 rounded-full bg-gradient-to-r from-[#7fe2cd] via-[#f2d884] to-[#bc4545]"
                    role="img"
                  >
                    {validPainLevel !== null && (
                      <span
                        className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-[#102d58] shadow-[0_1px_5px_rgba(8,38,76,0.5)]"
                        style={{ left: `${validPainLevel * 10}%` }}
                      />
                    )}
                  </div>
                  <div aria-hidden="true" className="mt-1 flex justify-between px-0.5 text-[11px] text-[#334b63]">
                    {Array.from({ length: 11 }, (_, value) => <span className={value === Math.round(validPainLevel ?? -1) ? "font-bold text-[#009bb4]" : ""} key={value}>{value}</span>)}
                  </div>
                  <p className="mt-3 text-right text-sm text-[#102d58]">
                    Pain level: <strong>{validPainLevel === null ? "—" : validPainLevel}</strong>
                    <span className="mx-2 text-[#a3b0bb]">·</span>
                    Certainty: <strong>{validConfidence === null ? "—" : `${Math.round(validConfidence * 100)}%`}</strong>
                  </p>
                </div>
              </div>
              {selectedResult && (
                <p className="mt-3 text-xs text-[#52677b]">
                  Model: <strong>{selectedResult.analysis.model_name}</strong> {selectedResult.analysis.model_version}
                  <span className="mx-2 text-[#a3b0bb]">·</span>
                  Status: <strong>{selectedResult.analysis.status}</strong>
                </p>
              )}
            </div>
            <div className="mt-4 border-t border-[#dce5e9] pt-3 text-[11px] text-[#52677b]">
              <strong className="block text-[#334b63]">Notice</strong>
              Remember that the model&apos;s result is only a help and does not constitute a substitution for a professional doctor&apos;s opinion.
            </div>
            {resultsTotal > 1 && (
              <div className="mt-4">
                <SectionTitle>Previous Model Evaluations</SectionTitle>
                <DataTable
                  columns={["Model", "Pain level", "Confidence", "Status", "Created"]}
                  currentPage={resultsPage}
                  itemLabel="evaluation"
                  itemLabelPlural="evaluations"
                  onPageChange={setResultsPage}
                  pageSize={20}
                  rows={resultRows}
                  selectable={false}
                  showToolbar={false}
                  totalCount={resultsTotal}
                />
              </div>
            )}
          </Surface>

          <Surface className="p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <SectionTitle>Patient’s Examination History</SectionTitle>
              <ButtonSecondary disabled={!historyTotal || isExportingHistory} icon="download" onClick={() => void downloadFullHistory()} type="button">
                {isExportingHistory ? "Exporting..." : "Export Full History"}
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

          {assessmentsTotal > 0 && (
            <details className="mt-4 rounded-[9px] border border-white/70 bg-white/[0.42] p-4 shadow-[0_3px_5px_rgba(0,0,0,0.22)] backdrop-blur-[8px]">
              <summary className="cursor-pointer text-lg font-semibold text-[#08264c]">
                Doctor Pain Assessments ({assessmentsTotal})
              </summary>
              <div className="mt-3">
                <DataTable
                  columns={["Pain level", "Scale", "Notes", "Assessed at"]}
                  currentPage={assessmentsPage}
                  itemLabel="pain assessment"
                  itemLabelPlural="pain assessments"
                  onPageChange={setAssessmentsPage}
                  pageSize={20}
                  rows={assessmentRows}
                  selectable={false}
                  showToolbar={false}
                  totalCount={assessmentsTotal}
                />
              </div>
            </details>
          )}
        </>
      )}
    </div>
  );
}

export default DoctorExaminationDetailsPage;
