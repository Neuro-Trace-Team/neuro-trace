import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable from "../../components/DataTable";
import Checkbox from "../../components/Checkbox";
import InputSection from "../../components/InputSection";
import { PageTitle, Surface } from "../../components/PageUI";
import { apiClient, getApiErrorMessage } from "../../services/apiClient";
import { formatDate } from "../../services/api";
import type { Examination, PaginatedResponse } from "../../types/api.types";
import { useAuth } from "../../context/useAuth";
import { useToast } from "../../context/useToast";

type ExaminationFilters = {
  patient_id: string;
  processing_status: string;
  date_from: string;
  date_to: string;
  channel: string;
  pain_level_min: string;
  pain_level_max: string;
  pain_source: "doctor" | "ai";
  sort_by: "created_at" | "examination_date" | "processing_status";
  sort_order: "asc" | "desc";
};

const emptyFilters: ExaminationFilters = {
  patient_id: "",
  processing_status: "",
  date_from: "",
  date_to: "",
  channel: "",
  pain_level_min: "",
  pain_level_max: "",
  pain_source: "doctor",
  sort_by: "created_at",
  sort_order: "desc",
};

function toApiDate(value: string) {
  return value ? new Date(value).toISOString() : undefined;
}

function DoctorExaminationsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [examinations, setExaminations] = useState<Examination[]>([]);
  const [total, setTotal] = useState(0);
  const [onlyMine, setOnlyMine] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState(emptyFilters);
  const [draftFilters, setDraftFilters] = useState(emptyFilters);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const { showToast } = useToast();

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const patientSearchId = /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(debouncedSearch)
    ? debouncedSearch
    : undefined;

  useEffect(() => {
    apiClient
      .get<PaginatedResponse<Examination>>("/examinations", {
        params: {
          page,
          page_size: 20,
          ...(onlyMine && user ? { uploaded_by: user.id } : {}),
          patient_id: patientSearchId || filters.patient_id || undefined,
          processing_status: filters.processing_status || undefined,
          date_from: toApiDate(filters.date_from),
          date_to: toApiDate(filters.date_to),
          channel: filters.channel || undefined,
          pain_level_min: filters.pain_level_min || undefined,
          pain_level_max: filters.pain_level_max || undefined,
          pain_source: filters.pain_source,
          sort_by: filters.sort_by,
          sort_order: filters.sort_order,
        },
      })
      .then(({ data }) => {
        setExaminations(data.items);
        setTotal(data.total);
      })
      .catch((loadError: unknown) => {
        showToast(getApiErrorMessage(loadError, "Could not load examinations."), "error");
      })
      .finally(() => setIsLoading(false));
  }, [debouncedSearch, filters, onlyMine, page, patientSearchId, showToast, user]);

  const updateDraft = <K extends keyof ExaminationFilters>(key: K, value: ExaminationFilters[K]) => {
    setDraftFilters((current) => ({ ...current, [key]: value }));
  };
  const filtersActive = Object.entries(filters).some(
    ([key, value]) => value !== emptyFilters[key as keyof ExaminationFilters],
  );

  const rows = examinations.map((examination) => [
    examination.id,
    formatDate(examination.examination_date ?? examination.created_at),
    examination.patient_id,
  ]);

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Browse Examinations</PageTitle>
      <Surface>
        <DataTable
          columns={["Examination ID", "Date", "Patient ID"]}
          itemLabel="examination"
          itemLabelPlural="examinations"
          onRowClick={(row) => navigate(`/doctor/examinations/${row[0]}`)}
          currentPage={page}
          onPageChange={(nextPage) => {
            setIsLoading(true);
            setPage(nextPage);
          }}
          pageSize={20}
          rows={rows}
          totalCount={total}
          searchPlaceholder="Search by patient UUID"
          searchValue={search}
          onSearchChange={(nextSearch) => {
            setSearch(nextSearch);
            setIsLoading(true);
            setPage(1);
          }}
          showFilters
          filtersActive={filtersActive}
          filterTitle="Filter examinations"
          onApplyFilters={() => {
            setIsLoading(true);
            setPage(1);
            setFilters(draftFilters);
          }}
          onClearFilters={() => {
            setDraftFilters(emptyFilters);
            setFilters(emptyFilters);
            setIsLoading(true);
            setPage(1);
          }}
          filterContent={(
            <div className="grid gap-4 sm:grid-cols-2">
              <InputSection label="Patient ID" name="patient-id-filter" onChange={(event) => updateDraft("patient_id", event.target.value)} placeholder="Patient UUID" value={draftFilters.patient_id} />
              <label className="grid gap-1 text-sm font-semibold text-[#102d58]">
                Processing status
                <select className="h-10 rounded-md border border-[#d6dfe3] bg-white px-3 outline-none focus:border-[#009bb4]" onChange={(event) => updateDraft("processing_status", event.target.value)} value={draftFilters.processing_status}>
                  <option value="">All statuses</option>
                  <option value="UPLOADED">Uploaded</option>
                  <option value="PREPROCESSING">Preprocessing</option>
                  <option value="READY">Ready</option>
                  <option value="FAILED">Failed</option>
                </select>
              </label>
              <InputSection label="Date from" name="examination-date-from" onChange={(event) => updateDraft("date_from", event.target.value)} type="datetime-local" value={draftFilters.date_from} />
              <InputSection label="Date to" name="examination-date-to" onChange={(event) => updateDraft("date_to", event.target.value)} type="datetime-local" value={draftFilters.date_to} />
              <InputSection label="EEG channel" maxLength={50} name="eeg-channel-filter" onChange={(event) => updateDraft("channel", event.target.value)} placeholder="e.g. C3" value={draftFilters.channel} />
              <div className="grid grid-cols-2 gap-3">
                <InputSection label="Pain from" inputClassName="min-w-0" min="0" name="pain-level-min" onChange={(event) => updateDraft("pain_level_min", event.target.value)} type="number" value={draftFilters.pain_level_min} />
                <InputSection label="Pain to" inputClassName="min-w-0" min="0" name="pain-level-max" onChange={(event) => updateDraft("pain_level_max", event.target.value)} type="number" value={draftFilters.pain_level_max} />
              </div>
              <label className="grid gap-1 text-sm font-semibold text-[#102d58]">
                Pain assessment source
                <select className="h-10 rounded-md border border-[#d6dfe3] bg-white px-3 outline-none focus:border-[#009bb4]" onChange={(event) => updateDraft("pain_source", event.target.value as ExaminationFilters["pain_source"])} value={draftFilters.pain_source}>
                  <option value="doctor">Doctor</option>
                  <option value="ai">AI</option>
                </select>
              </label>
              <label className="grid gap-1 text-sm font-semibold text-[#102d58]">
                Sort by
                <select className="h-10 rounded-md border border-[#d6dfe3] bg-white px-3 outline-none focus:border-[#009bb4]" onChange={(event) => updateDraft("sort_by", event.target.value as ExaminationFilters["sort_by"])} value={draftFilters.sort_by}>
                  <option value="created_at">Upload date</option>
                  <option value="examination_date">Examination date</option>
                  <option value="processing_status">Status</option>
                </select>
              </label>
              <label className="grid gap-1 text-sm font-semibold text-[#102d58]">
                Order
                <select className="h-10 rounded-md border border-[#d6dfe3] bg-white px-3 outline-none focus:border-[#009bb4]" onChange={(event) => updateDraft("sort_order", event.target.value as ExaminationFilters["sort_order"])} value={draftFilters.sort_order}>
                  <option value="desc">Descending</option>
                  <option value="asc">Ascending</option>
                </select>
              </label>
            </div>
          )}
          toolbarEnd={
            <div className="flex min-h-9 items-center rounded-lg border border-[#d6e1e6] bg-white/75 px-2.5">
              <Checkbox checked={onlyMine} label="Show my examinations only" onChange={(checked) => {
                setPage(1);
                setIsLoading(true);
                setOnlyMine(checked);
              }} />
            </div>
          }
        />
        {isLoading && <p className="mt-3 text-sm text-[#52677b]">Loading examinations...</p>}
      </Surface>
    </div>
  );
}

export default DoctorExaminationsPage;
