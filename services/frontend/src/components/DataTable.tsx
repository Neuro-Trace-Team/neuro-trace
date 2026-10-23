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
      {showToolbar && <div className="mb-4 flex flex-wrap items-center gap-2">
        <label className="relative min-w-[190px] flex-1 sm:max-w-[266px]">
          <Icon className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#66777f]" name="search" />
          <input
            aria-label={searchPlaceholder}
            className="h-8 w-full rounded-md border border-white/80 bg-white/65 pl-8 pr-3 text-[13px] outline-none placeholder:text-[#798388] focus:border-[#00a9c4]"
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

      <div className="overflow-x-auto rounded-[7px] bg-white shadow-[0_2px_4px_rgba(0,0,0,0.26)]">
        <table className="w-full min-w-[620px] border-collapse text-left text-[13px] leading-[20px] text-[#102d58]">
          <thead className="bg-[#061d4c] text-[14px] font-semibold text-white">
            <tr>
              {selectable && (
                <th className="w-8 px-2 py-1.5">
                  <input
                    aria-label="Select all rows"
                    checked={allSelected}
                    className="h-[14px] w-[14px] accent-[#00abc1]"
                    onChange={toggleAll}
                    type="checkbox"
                  />
                </th>
              )}
              {columns.map((column) => (
                <th className="whitespace-nowrap px-2 py-1.5 font-semibold" key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, visibleIndex) => {
              const rowIndex = rows.indexOf(row);
              return (
                <tr
                  className={`h-[22px] border-b border-[#e7eaec] last:border-0 ${onRowClick ? "cursor-pointer hover:bg-[#e9f8f9]" : "hover:bg-[#f4f8f9]"}`}
                  key={`${row.join("-")}-${rowIndex}`}
                  onClick={() => onRowClick?.(row)}
                >
                  {selectable && (
                    <td className="px-2 py-0">
                      <input
                        aria-label={`Select row ${visibleIndex + 1}`}
                        checked={selected.includes(rowIndex)}
                        className="h-[14px] w-[14px] accent-[#00abc1]"
                        onChange={() => setSelected((items) => items.includes(rowIndex) ? items.filter((item) => item !== rowIndex) : [...items, rowIndex])}
                        onClick={(event) => event.stopPropagation()}
                        type="checkbox"
                      />
                    </td>
                  )}
                  {row.map((cell, index) => (
                    <td className="max-w-[280px] truncate px-2 py-0" key={`${columns[index]}-${index}`} title={cell}>{cell}</td>
                  ))}
                </tr>
              );
            })}
            {visibleRows.length === 0 && (
              <tr><td className="px-4 py-8 text-center text-[#63717d]" colSpan={columns.length + Number(selectable)}>No results found.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showPagination && <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-[12px] text-[#18365d]">
        <span>
          Showing {filteredRows.length ? (page - 1) * pageSize + 1 : 0}–{Math.min(page * pageSize, filteredRows.length)} of {query ? filteredRows.length : totalCount ?? filteredRows.length} {columns[0]?.toLowerCase()}
        </span>
        <div aria-label="Pagination" className="flex items-center gap-1">
          <SmallButton aria-label="Previous page" className="h-8 w-8 px-1" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} type="button">
            <Icon className="h-4 w-4" name="left" />
          </SmallButton>
          {Array.from({ length: Math.min(3, pageCount) }, (_, index) => {
            const pageNumber = Math.min(Math.max(page - 1, 1) + index, pageCount);
            return (
              <SmallButton
                aria-current={page === pageNumber ? "page" : undefined}
                className={`h-8 min-w-8 px-2 ${page === pageNumber ? "bg-[#d9f0f1]" : ""}`}
                key={pageNumber}
                onClick={() => setPage(pageNumber)}
                type="button"
              >
                {pageNumber}
              </SmallButton>
            );
          })}
          <SmallButton aria-label="Next page" className="h-8 w-8 px-1" disabled={page >= pageCount} onClick={() => setPage((value) => value + 1)} type="button">
            <Icon className="h-4 w-4" name="right" />
          </SmallButton>
        </div>
      </div>}
    </div>
  );
}
