import axios from "axios";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import PageTitle from "../../components/PageTitle";
import SectionTitle from "../../components/SectionTitle";
import Surface from "../../components/Surface";
import { apiClient, getApiErrorMessage } from "../../services/apiClient";
import type { Examination } from "../../types/api.types";

type Analysis = { analysis_id: number; result: number | string; confidence: number | string };
type Results = { examination_id: string; analyses: Analysis[] };
export default function DoctorExaminationDetailsPage() {
  const { id } = useParams();
  const [exam, setExam] = useState<Examination | null>(null);
  const [results, setResults] = useState<Results | null>(null);
  const [state, setState] = useState("Loading results...");
  const [selected, setSelected] = useState<number | null>(null);
  useEffect(() => {
    if (!id) return;
    setExam(null); setResults(null); setSelected(null); setState("Loading results...");
    apiClient.get<Examination>(`/examinations/${id}`).then(({data}) => {
      setExam(data);

    }).catch(e => setState(getApiErrorMessage(e, "Could not load examination.")));
    apiClient.get<Results>(`/examinations/${id}/results`).then(({data}) => {
      setResults(data); setSelected(data.analyses[0]?.analysis_id ?? null);
      setState(data.analyses.length ? "Ready" : "No analyses available.");
    }).catch(e => setState(axios.isAxiosError(e) && e.response?.status === 409 ? "Analysis is being processed or is not ready yet." : getApiErrorMessage(e, "Results unavailable.")));
  }, [id]);
  const analysis = results?.analyses.find(x => x.analysis_id === selected);
  return <div className="mx-auto max-w-[1100px]"><PageTitle>Examination Results</PageTitle><Surface>
    {exam && <><SectionTitle>Examination</SectionTitle><p>Patient ID: {exam.patient_id}</p><p>File: {exam.original_filename}</p><p>Status: {exam.status}</p></>}
    <div className="mt-5"><SectionTitle>Model Evaluation</SectionTitle><p className="mb-3">{state}</p>
    {results && results.analyses.length > 0 && <div className="grid gap-4 md:grid-cols-2"><div className="max-h-48 space-y-1 overflow-y-auto" aria-label="Analyses">{results.analyses.map(item => <button type="button" key={item.analysis_id} onClick={() => setSelected(item.analysis_id)} className={`block w-full rounded-lg p-2 text-left ${selected === item.analysis_id ? "bg-cyan-100" : "bg-white"}`}>Analysis {item.analysis_id}</button>)}</div>{analysis && <div><p>Result: <strong>{analysis.result}</strong></p><p>Confidence: <strong>{Math.round(Number(analysis.confidence) * 100)}%</strong></p><p className="mt-2 text-sm">Timestamp data is not provided by the current results API.</p></div>}</div>}
    </div><p className="mt-5 text-sm">The model result supports, but does not replace, a professional medical opinion. PDF reports are not currently available.</p></Surface></div>;
}
