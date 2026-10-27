import { useMemo, useState } from "react";
import Icon from "./Icon";
import { SmallButton } from "./PageUI";

type DataTableProps = {
  columns: string[];
  rows: string[][];
  totalCount?: number;
  selectable?: boolean;
  searchPlaceholder?: string;
  showFilters?: boolean;
  showToolbar?: boolean;
  showPagination?: boolean;
  toolbarEnd?: React.ReactNode;
  onRowClick?: (row: string[]) => void;
};

export default function DataTable({
  columns,
  rows,
  totalCount,
  selectable = true,
  searchPlaceholder = "Search",
  showFilters = true,
  showToolbar = true,
  showPagination = true,
  toolbarEnd,
  onRowClick,
}: DataTableProps) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const pageSize = 20;
  const filteredRows = useMemo(
    () => rows.filter((row) => row.some((cell) => cell.toLowerCase().includes(query.toLowerCase()))),
    [query, rows],
  );
  const pageCount = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const visibleRows = filteredRows.slice((page - 1) * pageSize, page * pageSize);
  const allSelected = visibleRows.length > 0 && visibleRows.every((row) => selected.includes(rows.indexOf(row)));

  const toggleAll = () => {
    const visibleIndexes = visibleRows.map((row) => rows.indexOf(row));
    setSelected(allSelected ? selected.filter((index) => !visibleIndexes.includes(index)) : [...new Set([...selected, ...visibleIndexes])]);
  };

  const exportRows = () => {
    const selectedRows = selected.length ? rows.filter((_, index) => selected.includes(index)) : filteredRows;
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
      {showToolbar && <div className="mb-4 flex flex-wrap items-center gap-2.5">
        <label className="relative min-w-[200px] flex-1 sm:max-w-[300px]">
          <Icon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#718096]" name="search" />
          <input
            aria-label={searchPlaceholder}
            className="h-10 w-full rounded-lg border border-[#dce5e9] bg-white pl-10 pr-3 text-[13px] text-[#173456] shadow-sm outline-none transition placeholder:text-[#8997a2] focus:border-[#00a9c4] focus:ring-2 focus:ring-[#00b7c8]/15"
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder={searchPlaceholder}
            value={query}
          />
        </label>
        {showFilters && (
          <SmallButton type="button">
            <Icon className="h-4 w-4" name="filter" />
            Filters
          </SmallButton>
        )}
        {toolbarEnd}
        <SmallButton className="ml-auto" onClick={exportRows} type="button">
          <Icon className="h-4 w-4" name="download" />
          Export {selected.length ? "Selected" : "Data"}
        </SmallButton>
      </div>}

      <div className="overflow-x-auto rounded-xl border border-[#dce5e9] bg-white shadow-[0_4px_14px_rgba(8,38,76,0.07)]">
        <table className="w-full min-w-[680px] border-separate border-spacing-0 text-left text-[13px] leading-5 text-[#334b63]">
          <thead className="bg-[#f1f6f8] text-[11px] font-bold uppercase tracking-[0.07em] text-[#52677b]">
            <tr>
              {selectable && (
                <th className="w-12 border-b border-[#dce5e9] px-4 py-3.5">
                  <input
                    aria-label="Select all rows"
                    checked={allSelected}
                    className="h-4 w-4 cursor-pointer rounded border-[#b8c7d0] accent-[#00abc1] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#00a9c4]"
                    onChange={toggleAll}
                    type="checkbox"
                  />
                </th>
              )}
              {columns.map((column) => (
                <th className="whitespace-nowrap border-b border-[#dce5e9] px-4 py-3.5 font-bold" key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, visibleIndex) => {
              const rowIndex = rows.indexOf(row);
              return (
                <tr
                  className={`group transition-colors items-center ${onRowClick ? "cursor-pointer" : ""} ${
                    selected.includes(rowIndex)
                      ? "bg-[#eaf8fa] hover:bg-[#e3f5f7]"
                      : "bg-white even:bg-[#f8fafb] hover:bg-[#f0f8f9]"
                  }`}
                  key={`${row.join("-")}-${rowIndex}`}
                  onClick={() => onRowClick?.(row)}
                >
                  {selectable && (
                    <td className="border-b border-[#edf1f3] px-4 py-1.5 group-last:border-0" onClick={(e) => {e.stopPropagation();setSelected((items) => items.includes(rowIndex) ? items.filter((item) => item !== rowIndex) : [...items, rowIndex])}}>
                      <input
                        aria-label={`Select row ${visibleIndex + 1}`}
                        checked={selected.includes(rowIndex)}
                        className="h-4 w-4 cursor-pointer rounded border-[#b8c7d0] accent-[#00abc1] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#00a9c4]"
                        onChange={() => setSelected((items) => items.includes(rowIndex) ? items.filter((item) => item !== rowIndex) : [...items, rowIndex])}
                        onClick={(e) => e.stopPropagation()}
                        type="checkbox"
                      />
                    </td>
                  )}
                  {row.map((cell, index) => (
                    <td
                      className={`max-w-[420px] truncate border-b border-[#edf1f3] px-4 py-2.5 group-last:border-0 ${
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
          Showing {filteredRows.length ? (page - 1) * pageSize + 1 : 0}–{Math.min(page * pageSize, filteredRows.length)} of {query ? filteredRows.length : totalCount ?? filteredRows.length} {columns[0]?.toLowerCase()}
        </span>
        <div aria-label="Pagination" className="flex items-center gap-1.5">
          <SmallButton aria-label="Previous page" className="h-9 w-9 rounded-lg border-[#dce5e9] px-1 shadow-none" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} type="button">
            <Icon className="h-4 w-4" name="left" />
          </SmallButton>
          {Array.from({ length: Math.min(3, pageCount) }, (_, index) => {
            const pageNumber = Math.min(Math.max(page - 1, 1) + index, pageCount);
            return (
              <SmallButton
                aria-current={page === pageNumber ? "page" : undefined}
                className={`h-9 min-w-9 rounded-lg border-[#dce5e9] px-2 shadow-none ${
                  page === pageNumber
                    ? "border-[#9adce3] bg-[#e8f8fa] font-bold text-[#07516a]"
                    : ""
                }`}
                key={pageNumber}
                onClick={() => setPage(pageNumber)}
                type="button"
              >
                {pageNumber}
              </SmallButton>
            );
          })}
          <SmallButton aria-label="Next page" className="h-9 w-9 rounded-lg border-[#dce5e9] px-1 shadow-none" disabled={page >= pageCount} onClick={() => setPage((value) => value + 1)} type="button">
            <Icon className="h-4 w-4" name="right" />
          </SmallButton>
        </div>
      </div>}
    </div>
  );
}
