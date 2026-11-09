import { useCallback, useId, useMemo, useState } from "react";
import ButtonPrimary from "./ButtonPrimary";
import ButtonSecondary from "./ButtonSecondary";
import Checkbox from "./Checkbox";
import Icon from "./Icon";
import InputSection from "./InputSection";
import Modal from "./Modal";

type DataTableProps = {
  columns: string[];
  rows: string[][];
  rowIds?: string[];
  totalCount?: number;
  selectable?: boolean;
  searchPlaceholder?: string;
  showFilters?: boolean;
  showToolbar?: boolean;
  showPagination?: boolean;
  toolbarEnd?: React.ReactNode;
  onRowClick?: (row: string[], rowIndex: number) => void;
  currentPage?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  filterContent?: React.ReactNode;
  onApplyFilters?: () => void;
  onClearFilters?: () => void;
  filtersActive?: boolean;
  filterTitle?: string;
  filterButtonLabel?: string;
  itemLabel?: string;
  itemLabelPlural?: string;
  searchValue?: string;
  onSearchChange?: (query: string) => void;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
  sortableColumns?: Record<string, string>;
  onSortChange?: (sortBy: string, sortOrder: "asc" | "desc") => void;
  sortable?: boolean;
};

export default function DataTable({
  columns,
  rows,
  rowIds,
  totalCount,
  selectable = true,
  searchPlaceholder = "Search",
  showFilters = false,
  showToolbar = true,
  showPagination = true,
  toolbarEnd,
  onRowClick,
  currentPage,
  pageSize = 20,
  onPageChange,
  filterContent,
  onApplyFilters,
  onClearFilters,
  filtersActive = false,
  filterTitle = "Filters",
  filterButtonLabel = "Filters",
  itemLabel = "record",
  itemLabelPlural = `${itemLabel}s`,
  searchValue,
  onSearchChange,
  sortBy,
  sortOrder,
  sortableColumns,
  onSortChange,
  sortable = true,
}: DataTableProps) {
  const [localQuery, setLocalQuery] = useState("");
  const [localPage, setLocalPage] = useState(1);
  const [pageInputState, setPageInputState] = useState({ page: currentPage ?? 1, value: String(currentPage ?? 1) });
  const pageInput = pageInputState.page === (currentPage ?? localPage) ? pageInputState.value : String(currentPage ?? localPage);
  const setPageInput = (value: string) => setPageInputState({ page: currentPage ?? localPage, value });
  const pageInputId = useId();
  const [selected, setSelected] = useState<string[]>([]);
  const [localSort, setLocalSort] = useState<{ columnIndex: number; order: "asc" | "desc" } | null>(null);
  const [isFilterModalOpen, setIsFilterModalOpen] = useState(false);
  const closeFilterModal = useCallback(() => setIsFilterModalOpen(false), []);
  const page = currentPage ?? localPage;
  const serverPagination = currentPage !== undefined && onPageChange !== undefined;
  const serverSearch = onSearchChange !== undefined;
  const query = searchValue ?? localQuery;
  const changePage = (nextPage: number) => {
    const boundedPage = Math.min(Math.max(nextPage, 1), pageCount);
    setPageInput(String(boundedPage));
    if (serverPagination) {
      setSelected([]);
      onPageChange(boundedPage);
    } else {
      setLocalPage(boundedPage);
    }
  };
  const filteredRows = useMemo(
    () => serverSearch || !query
      ? rows
      : rows.filter((row) => row.some((cell) => cell.toLowerCase().includes(query.toLowerCase()))),
    [query, rows, serverSearch],
  );
  const sortedRows = useMemo(() => {
    if (!localSort) return filteredRows;
    return [...filteredRows].sort((first, second) => {
      const firstValue = first[localSort.columnIndex] ?? "";
      const secondValue = second[localSort.columnIndex] ?? "";
      const firstNumber = Number(firstValue);
      const secondNumber = Number(secondValue);
      const comparison = firstValue.trim() && secondValue.trim() && Number.isFinite(firstNumber) && Number.isFinite(secondNumber)
        ? firstNumber - secondNumber
        : firstValue.localeCompare(secondValue, undefined, { numeric: true, sensitivity: "base" });
      return localSort.order === "asc" ? comparison : -comparison;
    });
  }, [filteredRows, localSort]);
  const pageCount = Math.max(
    1,
    Math.ceil((serverPagination ? totalCount ?? rows.length : filteredRows.length) / pageSize),
  );
  const visibleRows = serverPagination
    ? localSort ? sortedRows : filteredRows
    : sortedRows.slice((page - 1) * pageSize, page * pageSize);
  const resultCount = serverPagination ? totalCount ?? rows.length : sortedRows.length;
  const rowId = (row: string[]) => rowIds?.[rows.indexOf(row)] ?? row[0];
  const allSelected = visibleRows.length > 0 && visibleRows.every((row) => selected.includes(rowId(row)));

  const toggleAll = () => {
    const visibleIndexes = visibleRows.map((row) => rowId(row));
    setSelected(allSelected ? selected.filter((index) => !visibleIndexes.includes(index)) : [...new Set([...selected, ...visibleIndexes])]);
  };

  const sortColumn = (column: string, columnIndex: number) => {
    const serverSortColumn = sortableColumns?.[column];
    if (serverSortColumn && onSortChange) {
      const nextOrder = sortBy === serverSortColumn && sortOrder === "asc" ? "desc" : "asc";
      setLocalSort(null);
      onSortChange(serverSortColumn, nextOrder);
      return;
    }

    setLocalSort((current) => ({
      columnIndex,
      order: current?.columnIndex === columnIndex && current.order === "asc" ? "desc" : "asc",
    }));
  };

  const exportRows = () => {
    const selectedRows = selected.length ? rows.filter((row) => selected.includes(rowId(row))) : visibleRows;
    const csv = [columns, ...selectedRows].map((row) => row.map((cell) => `"${cell.replaceAll('"', '""')}"`).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "neurotrace-export.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-w-0">
      {showToolbar && <div className="mb-4 flex flex-wrap items-end gap-2.5">
        <InputSection
          aria-label={searchPlaceholder}
          className="min-w-[200px] flex-1 sm:max-w-[300px]"
          onChange={(event) => {
            const nextQuery = event.target.value;
            if (serverSearch) onSearchChange(nextQuery);
            else setLocalQuery(nextQuery);
            changePage(1);
          }}
          onClear={() => {
            if (serverSearch) onSearchChange("");
            else setLocalQuery("");
            changePage(1);
          }}
          placeholder={searchPlaceholder}
          type="text"
          value={query}
        />
        {showFilters && (
          <ButtonSecondary aria-pressed={filtersActive} icon="filter" onClick={() => setIsFilterModalOpen(true)} type="button">
            {filterButtonLabel}{filtersActive ? " •" : ""}
          </ButtonSecondary>
        )}
        {toolbarEnd}
        <ButtonSecondary className="ml-auto" icon="download" onClick={exportRows} type="button">
          Export {selected.length ? "Selected" : "Page"}
        </ButtonSecondary>
      </div>}

      <div className="overflow-x-auto rounded-xl border border-[#dce5e9] bg-white shadow-[0_4px_14px_rgba(8,38,76,0.07)]">
        <table className="w-full min-w-[680px] border-separate border-spacing-0 text-left text-[13px] leading-5 text-[#334b63]">
          <thead className="bg-[#f1f6f8] text-[11px] font-bold uppercase tracking-[0.07em] text-[#52677b]">
            <tr>
              {selectable && (
                <th className="w-12 border-b border-[#dce5e9] px-4 py-3.5">
                  <Checkbox checked={allSelected} label="Select all rows" onChange={toggleAll} showLabel={false} />
                </th>
              )}
              {columns.map((column, columnIndex) => {
                if (!sortable || (serverPagination && !sortableColumns?.[column])) {
                  return (
                    <th className="whitespace-nowrap border-b border-[#dce5e9] px-4 py-3.5 font-bold" key={column}>
                      {column}
                    </th>
                  );
                }
                const serverSortColumn = sortableColumns?.[column];
                const isServerSorted = Boolean(serverSortColumn && sortBy === serverSortColumn);
                const isLocallySorted = !isServerSorted && localSort?.columnIndex === columnIndex;
                const activeOrder = isServerSorted ? sortOrder : isLocallySorted ? localSort?.order : undefined;
                return (
                  <th
                    aria-sort={activeOrder ? (activeOrder === "asc" ? "ascending" : "descending") : "none"}
                    className="whitespace-nowrap border-b border-[#dce5e9] px-4 py-3.5 font-bold"
                    key={column}
                  >
                    <button
                      className="inline-flex cursor-pointer items-center gap-1.5 text-left hover:text-[#0876b5]"
                      onClick={() => sortColumn(column, columnIndex)}
                      type="button"
                    >
                      {column}
                      <Icon className={`h-3.5 w-3.5 ${activeOrder ? "text-[#0876b5]" : "opacity-40"}`} name={activeOrder === "asc" ? "sortAsc" : activeOrder === "desc" ? "sortDesc" : "sort"} />
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, visibleIndex) => {
              const rowIndex = rows.indexOf(row);
              return (
                <tr
                  className={`group items-center transition-[background-color,box-shadow] duration-150 ease-out ${
                    onRowClick
                      ? "cursor-pointer hover:bg-[#eaf8fa] active:bg-[#ddf3f5] motion-reduce:transition-none"
                      : ""
                  } ${
                    selected.includes(rowId(row))
                      ? "bg-[#eaf8fa] even:bg-[#eaf8fa]"
                      : "bg-white even:bg-[#f7fafb]"
                  }`}
                  key={`${row.join("-")}-${rowIndex}`}
                  onClick={() => onRowClick?.(row, rowIndex)}
                  onKeyDown={(event) => {
                    if (onRowClick && (event.key === "Enter" || event.key === " ")) {
                      event.preventDefault();
                      onRowClick(row, rowIndex);
                    }
                  }}
                  tabIndex={onRowClick ? 0 : undefined}
                >
                  {selectable && (
                    <td className="border-b border-[#edf1f3] px-4 py-2.5 group-last:border-0">
                      <div onClick={(event) => event.stopPropagation()}>
                        <Checkbox
                          checked={selected.includes(rowId(row))}
                          label={`Select row ${visibleIndex + 1}`}
                          onChange={() => setSelected((items) => items.includes(rowId(row)) ? items.filter((item) => item !== rowId(row)) : [...items, rowId(row)])}
                          showLabel={false}
                        />
                      </div>
                    </td>
                  )}
                  {row.map((cell, index) => (
                    <td
                      className={`max-w-[420px] truncate border-b border-[#edf1f3] px-4 py-3.5 group-last:border-0 ${
                        index === 0 ? "font-semibold text-[#102d58]" : ""
                      }`}
                      key={`${columns[index]}-${index}`}
                      title={cell}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              );
            })}
            {visibleRows.length === 0 && (
              <tr>
                <td
                  className="px-4 py-14 text-center text-[13px] text-[#718096]"
                  colSpan={columns.length + Number(selectable)}
                >
                  <span className="mb-1 block font-semibold text-[#334b63]">No matching records</span>
                  Try adjusting your search and try again.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showPagination && <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-[#e5ecef] pt-3 text-[12px] text-[#62768a]">
        <span>
          Showing {resultCount ? (page - 1) * pageSize + 1 : 0}–{Math.min(page * pageSize, resultCount)} of {resultCount} {resultCount === 1 ? itemLabel : itemLabelPlural}
        </span>
        <div aria-label="Pagination" className="flex items-center gap-1.5">
          <ButtonSecondary aria-label="Previous page" className="h-9 w-9 rounded-lg px-1 shadow-none" disabled={page <= 1} icon="left" iconOnly onClick={() => changePage(page - 1)} type="button" />
          <ButtonSecondary aria-label={page > 1 ? `Go to page ${page - 1}` : "No previous page"} className="h-9 min-w-9 px-2" disabled={page <= 1} onClick={() => changePage(page - 1)} type="button">{Math.max(1, page - 1)}</ButtonSecondary>
          <InputSection
            aria-label={`Current page, ${page} of ${pageCount}`}
            className="w-14"
            inputMode="numeric"
            inputClassName="h-9 border-[#9adce3] bg-[#e8f8fa] px-1 text-center text-sm font-bold text-[#07516a] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none [-moz-appearance:textfield]"
            name={pageInputId}
            max={pageCount}
            min={1}
            step={1}
            onBlur={() => {
              const nextPage = Number(pageInput);
              if (Number.isInteger(nextPage) && nextPage >= 1 && nextPage <= pageCount) changePage(nextPage);
              else setPageInput(String(page));
            }}
            onChange={(event) => setPageInput(event.target.value.replace(/\D/g, ""))}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.currentTarget.blur();
              }
            }}
            value={pageInput}
            type="number"
          />
          <ButtonSecondary aria-label={page < pageCount ? `Go to page ${page + 1}` : "No next page"} className="h-9 min-w-9 px-2" disabled={page >= pageCount} onClick={() => changePage(page + 1)} type="button">{Math.min(pageCount, page + 1)}</ButtonSecondary>
          <ButtonSecondary aria-label="Next page" className="h-9 w-9 rounded-lg px-1 shadow-none" disabled={page >= pageCount} icon="right" iconOnly onClick={() => changePage(page + 1)} type="button" />
        </div>
      </div>}
      {isFilterModalOpen && filterContent && (
        <Modal
          title={filterTitle}
          onClose={closeFilterModal}
          footer={(
            <>
              {onClearFilters && (
                <ButtonSecondary onClick={() => {
                  onClearFilters();
                  changePage(1);
                  closeFilterModal();
                }} type="button">
                  Clear filters
                </ButtonSecondary>
              )}
              <ButtonPrimary
                onClick={() => {
                  onApplyFilters?.();
                  changePage(1);
                  closeFilterModal();
                }}
                type="button"
              >
                Apply filters
              </ButtonPrimary>
            </>
          )}
        >
          {filterContent}
        </Modal>
      )}
    </div>
  );
}
