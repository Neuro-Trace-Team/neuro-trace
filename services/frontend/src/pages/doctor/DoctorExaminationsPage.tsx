import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import DataTable from "../../components/DataTable";
import Checkbox from "../../components/Checkbox";
import InputSection from "../../components/InputSection";
import PageTitle from "../../components/PageTitle";
import Surface from "../../components/Surface";
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
};
type SortField = "created_at" | "examination_date" | "processing_status";
type SortOrder = "asc" | "desc";

function toApiDate(value: string) {
  return value ? new Date(value).toISOString() : undefined;
}

function DoctorExaminationsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
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
          date_from: toApiDate(filters.date_from),
          date_to: toApiDate(filters.date_to),
          sort_by: sortBy,
          sort_order: sortOrder,
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
  }, [debouncedSearch, filters, onlyMine, page, patientSearchId, showToast, sortBy, sortOrder, user]);

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
          sortBy={sortBy}
          sortOrder={sortOrder}
          sortableColumns={{ Date: "examination_date" }}
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
              <InputSection label="Date from" name="examination-date-from" onChange={(event) => updateDraft("date_from", event.target.value)} type="datetime-local" value={draftFilters.date_from} />
              <InputSection label="Date to" name="examination-date-to" onChange={(event) => updateDraft("date_to", event.target.value)} type="datetime-local" value={draftFilters.date_to} />
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
        {search && !patientSearchId && <p className="mt-3 text-sm">Enter a complete patient UUID to filter results.</p>}
        {isLoading && <p className="mt-3 text-sm text-[#52677b]">Loading examinations...</p>}
      </Surface>
    </div>
  );
}

export default DoctorExaminationsPage;
