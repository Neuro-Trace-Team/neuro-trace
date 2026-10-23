function GlassPane({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`
    border border-white/55
    bg-white/[0.18]
    backdrop-blur-[12px]
    backdrop-saturate-[120%]
    rounded-[14px]
    shadow-[inset_0_1px_0_rgba(255,255,255,0.65),0_3px_7px_rgba(5,45,65,0.24)]
    ${className || ''}`}>
      {children}
    </div>
  );
}

export default GlassPane;