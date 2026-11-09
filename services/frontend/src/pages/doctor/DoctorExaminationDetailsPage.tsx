import axios from "axios";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ButtonSecondary from "../../components/ButtonSecondary";
import DataTable from "../../components/DataTable";
import PageTitle from "../../components/PageTitle";
import SectionTitle from "../../components/SectionTitle";
import Surface from "../../components/Surface";
import { apiClient, getApiErrorMessage } from "../../services/apiClient";
import { formatExaminationDate } from "../../services/api";
import type { Examination, PaginatedResponse } from "../../types/api.types";

type Analysis = { analysis_id: number; result: number | string; confidence: number | string };
type Results = { examination_id: string; analyses: Analysis[] };
type HistoryItem = { id: string; examination_date: string | null };

function ModelEvaluation({ id }: { id: string }) {
  const navigate = useNavigate();
  const [exam, setExam] = useState<Examination | null>(null);
  const [examError, setExamError] = useState("");
  const [results, setResults] = useState<Results | null>(null);
  const [resultsMessage, setResultsMessage] = useState("Loading results...");
  const [selected, setSelected] = useState<number | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyMessage, setHistoryMessage] = useState("Loading examination history...");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");

  useEffect(() => {
    let active = true;
    apiClient.get<Examination>(`/examinations/${id}`)
      .then(({ data }) => { if (active) setExam(data); })
      .catch((error: unknown) => { if (active) setExamError(getApiErrorMessage(error, "Could not load examination.")); });
    apiClient.get<Results>(`/examinations/${id}/results`)
      .then(({ data }) => {
        if (!active) return;
        setResults(data);
        setSelected(data.analyses[0]?.analysis_id ?? null);
        setResultsMessage(data.analyses.length ? "" : "No analyses available.");
      })
      .catch((error: unknown) => {
        if (active) setResultsMessage(axios.isAxiosError(error) && error.response?.status === 409 ? "Analysis is being processed or is not ready yet." : getApiErrorMessage(error, "Results unavailable."));
      });
    return () => { active = false; };
  }, [id]);

  useEffect(() => {
    if (!exam) return;
    let active = true;
    apiClient.get<PaginatedResponse<HistoryItem>>(`/patients/${exam.patient_id}/examinations`, { params: { page: historyPage, page_size: 10 } })
      .then(({ data }) => { if (active) { setHistory(data.items); setHistoryTotal(data.total); setHistoryMessage(""); } })
      .catch((error: unknown) => { if (active) setHistoryMessage(getApiErrorMessage(error, "Could not load examination history.")); });
    return () => { active = false; };
  }, [exam, historyPage]);

  const exportHistory = async () => {
    if (!exam) return;
    setExporting(true);
    setExportError("");
    try {
      const first = await apiClient.get<PaginatedResponse<HistoryItem>>(`/patients/${exam.patient_id}/examinations`, { params: { page: 1, page_size: 100 } });
      const items = [...first.data.items];
      const pages = Math.ceil(first.data.total / first.data.page_size);
      for (let page = 2; page <= pages; page += 1) {
        const response = await apiClient.get<PaginatedResponse<HistoryItem>>(`/patients/${exam.patient_id}/examinations`, { params: { page, page_size: 100 } });
        items.push(...response.data.items);
      }
      const csv = ["Examination ID,Examination date", ...items.map((item) => `${item.id},${formatExaminationDate(item.examination_date)}`)].join("\r\n");
      const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `examination-history-${exam.patient_id}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setExportError(getApiErrorMessage(error, "Could not export examination history."));
    } finally {
      setExporting(false);
    }
  };

  const analysis = results?.analyses.find((item) => item.analysis_id === selected);
  const painLevel = analysis ? Number(analysis.result) : NaN;
  const hasPainLevel = Number.isFinite(painLevel) && painLevel >= 0 && painLevel <= 10;

  return (
    <>
      <Surface>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <SectionTitle>Model Evaluation</SectionTitle>
            <p className="break-all text-sm text-[#173456]">Examination ID: <strong>{id}</strong></p>
            {exam && <p className="mt-1 break-all text-sm text-[#173456]">Patient ID: <strong>{exam.patient_id}</strong></p>}
            {examError && <p className="mt-1 text-sm text-red-700" role="alert">{examError}</p>}
          </div>
          <ButtonSecondary disabled icon="download" title="Report export is not available" type="button">Export Report</ButtonSecondary>
        </div>
        <div className="mt-4 rounded-xl border border-white/80 bg-white/45 p-4 shadow-[0_4px_14px_rgba(8,38,76,0.06)]">
          <h3 className="mb-3 text-lg font-semibold text-[#102d58]">Detected Pain Levels</h3>
          {resultsMessage && <p className="py-6 text-sm text-[#52677b]" role="status">{resultsMessage}</p>}
          {results && results.analyses.length > 0 && (
            <div className="grid gap-5 md:grid-cols-[minmax(180px,0.65fr)_minmax(0,1.35fr)] md:gap-10">
              <div aria-label="Analyses" className="max-h-56 space-y-1 overflow-y-auto pr-1">
                {results.analyses.map((item) => (
                  <button aria-pressed={item.analysis_id === selected} className={`flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left text-sm text-[#102d58] transition-colors focus-visible:outline-2 focus-visible:outline-[#00a9c4] ${item.analysis_id === selected ? "border-white bg-white/80 shadow-md" : "border-white bg-white/20 hover:bg-white/60"}`} key={item.analysis_id} onClick={() => setSelected(item.analysis_id)} type="button">
                    <span>Analysis {item.analysis_id}</span><strong>{item.result}</strong>
                  </button>
                ))}
              </div>
              {analysis && <div className="flex min-w-0 flex-col justify-center py-3">
                {hasPainLevel ? <>
                  <div aria-label={`Pain level ${painLevel} out of 10`} className="relative h-5 rounded-full bg-gradient-to-r from-[#8de2cb] via-[#e8df9d] to-[#a8393e]">
                    <span aria-hidden="true" className="absolute left-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-gradient-to-r from-white/0 via-white/35 to-white/90" style={{ width: `${painLevel * 10}%` }} />
                    <span aria-hidden="true" className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white shadow-[0_0_5px_2px_rgba(255,255,255,0.95),0_0_13px_5px_rgba(255,255,255,0.6)]" style={{ left: `${painLevel * 10}%` }} />
                  </div>
                  <div aria-hidden="true" className="mt-2 flex justify-between text-xs text-[#173456]">{Array.from({ length: 11 }, (_, index) => <span className={index === painLevel ? "font-bold text-[#009bb4]" : ""} key={index}>{index}</span>)}</div>
                </> : <p className="text-sm text-[#52677b]">Result: {analysis.result} (outside the displayed 0–10 scale)</p>}
                <p className="mt-7 text-right text-lg text-[#102d58]">Confidence: <strong>{Math.round(Number(analysis.confidence) * 100)}%</strong></p>
              </div>}
            </div>
          )}
        </div>
        <div className="mt-4 px-2 text-xs leading-5 text-[#173456]"><strong className="block">Notice</strong>The model result supports, but does not replace, a professional medical opinion.</div>
      </Surface>
      <Surface>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <SectionTitle>Patient’s Examination History</SectionTitle>
          <ButtonSecondary disabled={!exam || exporting} icon="download" onClick={() => void exportHistory()} type="button">{exporting ? "Exporting..." : "Export Full History (CSV)"}</ButtonSecondary>
        </div>
        {exportError && <p className="mb-3 text-sm text-red-700" role="alert">{exportError}</p>}
        {historyMessage ? <p className="py-6 text-sm text-[#52677b]" role="status">{examError ? "Examination history unavailable." : historyMessage}</p> : (
          <DataTable columns={["Examination ID", "Date"]} currentPage={historyPage} itemLabel="examination" itemLabelPlural="examinations" onPageChange={setHistoryPage} onRowClick={(row) => navigate(`/doctor/examinations/${row[0]}`)} pageSize={10} rowIds={history.map((item) => item.id)} rows={history.map((item) => [item.id, formatExaminationDate(item.examination_date)])} selectable={false} showToolbar={false} sortable={false} totalCount={historyTotal} />
        )}
      </Surface>
    </>
  );
}

export default function DoctorExaminationDetailsPage() {
  const { id } = useParams();
  return <div className="mx-auto max-w-[1100px]"><PageTitle>Examination Results</PageTitle><div className="space-y-3">{id && <ModelEvaluation id={id} key={id} />}</div></div>;
}
