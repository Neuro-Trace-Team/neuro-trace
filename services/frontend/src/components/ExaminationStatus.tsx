const statusStyles: Record<string, string> = {
  READY: "border-[#b5ddce]/80 from-white/65 to-[#d5f0e3]/55 text-[#17613f]",
  PREPROCESSING: "border-[#b1dce4]/80 from-white/65 to-[#d7eef4]/55 text-[#176079]",
};

export default function ExaminationStatus({ status }: { status: string }) {
  const label = status.toLowerCase().replaceAll("_", " ");
  return (
    <span className={` inline-flex items-center rounded-lg border bg-gradient-to-br px-2.5 py-1 text-xs font-semibold capitalize shadow-[inset_0_1px_1px_rgba(255,255,255,0.8),0_1px_3px_rgba(8,38,76,0.06)] backdrop-blur-sm ${statusStyles[status] ?? "border-white/80 from-white/65 to-white/30 text-[#52677b]"}`}>
      {label}
    </span>
  );
}
