import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import DataTable from "../../components/DataTable";
import ExaminationStatus from "../../components/ExaminationStatus";
import Checkbox from "../../components/Checkbox";
import InputSection from "../../components/InputSection";
import PageTitle from "../../components/PageTitle";
import Surface from "../../components/Surface";
import { apiClient, getApiErrorMessage } from "../../services/apiClient";
import { formatExaminationDate } from "../../services/api";
import type { Examination, PaginatedResponse } from "../../types/api.types";
import { useAuth } from "../../context/useAuth";
import { useToast } from "../../context/useToast";

type ExaminationFilters = { id: string; patient_id: string; uploaded_by: string; status: string; date_from: string; date_to: string };
const emptyFilters: ExaminationFilters = { id: "", patient_id: "", uploaded_by: "", status: "", date_from: "", date_to: "" };
type SortField = "created_at" | "examination_date" | "id" | "patient_id" | "status";
type SortOrder = "asc" | "desc";

function toApiDate(value: string) {
  return value ? new Date(value).toISOString() : undefined;
}

function DoctorExaminationsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const [statuses, setStatuses] = useState<string[]>([]);
  const [examinations, setExaminations] = useState<Examination[]>([]);
  const [total, setTotal] = useState(0);
  const [onlyMine, setOnlyMine] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState(emptyFilters);
  const [draftFilters, setDraftFilters] = useState(emptyFilters);
  const [sortBy, setSortBy] = useState<SortField>("created_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [search, setSearch] = useState(searchParams.get("patient_id") ?? "");
  const [debouncedSearch, setDebouncedSearch] = useState(searchParams.get("patient_id") ?? "");
  const { showToast } = useToast();

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    apiClient.get<{ statuses: string[] }>("/examinations/statuses")
      .then(({ data }) => setStatuses(data.statuses))
      .catch((error: unknown) => showToast(getApiErrorMessage(error, "Could not load examination statuses."), "error"));
  }, [showToast]);

  useEffect(() => {
    let active = true;
    apiClient
      .get<PaginatedResponse<Examination>>("/examinations", {
        params: {
          page,
          page_size: 20,
          query: debouncedSearch || undefined,
          id: filters.id || undefined,
          uploaded_by: onlyMine && user ? user.id : filters.uploaded_by || undefined,
          patient_id: filters.patient_id || undefined,
          status: filters.status || undefined,
          examination_date_from: toApiDate(filters.date_from),
          examination_date_to: toApiDate(filters.date_to),
          sort_by: sortBy,
          sort_order: sortOrder,
        },
      })
      .then(({ data }) => {
        if (!active) return;
        setExaminations(data.items);
        setTotal(data.total);
      })
      .catch((loadError: unknown) => {
        if (active) showToast(getApiErrorMessage(loadError, "Could not load examinations."), "error");
      })
      .finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, [debouncedSearch, filters, onlyMine, page, showToast, sortBy, sortOrder, user]);

  const updateDraft = <K extends keyof ExaminationFilters>(key: K, value: ExaminationFilters[K]) => {
    setDraftFilters((current) => ({ ...current, [key]: value }));
  };
  const filtersActive = Object.entries(filters).some(
    ([key, value]) => value !== emptyFilters[key as keyof ExaminationFilters],
  );

  const rows = examinations.map((examination) => [
    examination.id,
    examination.patient_id,
    formatExaminationDate(examination.examination_date),
    examination.status,
  ]);

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Browse Examinations</PageTitle>
      <Surface>
        <DataTable
          columns={["Examination ID", "Patient ID", "Examination date", "Status"]}
          renderCell={(value, index) => index === 3 ? <ExaminationStatus status={value} /> : value}
          sortBy={sortBy}
          sortOrder={sortOrder}
          sortableColumns={{ "Examination ID": "id", "Patient ID": "patient_id", "Examination date": "examination_date", Status: "status" }}
          onSortChange={(nextSortBy, nextSortOrder) => {
            setIsLoading(true);
            setPage(1);
            setSortBy(nextSortBy as SortField);
            setSortOrder(nextSortOrder);
          }}
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
          searchPlaceholder="Search examination or patient ID"
          searchValue={search}
          onSearchChange={(nextSearch) => {
            setSearch(nextSearch);
            setPage(1);
          }}
          showFilters
          filtersActive={filtersActive}
          filterTitle="Filter examinations"
          onApplyFilters={() => {
            setIsLoading(true);
            setPage(1);
            setFilters({ ...draftFilters });
          }}
          onClearFilters={() => {
            setDraftFilters(emptyFilters);
            setFilters({ ...emptyFilters });
            setIsLoading(true);
            setPage(1);
          }}
          filterContent={(
            <div className="grid gap-4 sm:grid-cols-2">
              <InputSection label="Examination ID" name="exam-id-filter" value={draftFilters.id} onChange={(event) => updateDraft("id", event.target.value)} />
              <InputSection label="Uploaded by user ID" name="uploader-filter" value={draftFilters.uploaded_by} onChange={(event) => updateDraft("uploaded_by", event.target.value)} />
              <label className="grid gap-1 text-sm font-semibold text-[#102d58]">Status<select className="h-10 rounded-md border border-[#d6dfe3] bg-white px-3" value={draftFilters.status} onChange={(event) => updateDraft("status", event.target.value)}><option value="">All statuses</option>{statuses.map((status) => <option key={status} value={status}>{status}</option>)}</select></label>
              <InputSection label="Patient ID" name="patient-id-filter" onChange={(event) => updateDraft("patient_id", event.target.value)} placeholder="Patient UUID" value={draftFilters.patient_id} />
              <InputSection label="Examination date from" name="examination-date-from" onChange={(event) => updateDraft("date_from", event.target.value)} type="datetime-local" value={draftFilters.date_from} />
              <InputSection label="Examination date to" name="examination-date-to" onChange={(event) => updateDraft("date_to", event.target.value)} type="datetime-local" value={draftFilters.date_to} />
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
