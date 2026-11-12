import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import ButtonSecondary from "./ButtonSecondary";

type ModalProps = {
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  closeLabel?: string;
};

export default function Modal({
  title,
  description,
  onClose,
  children,
  footer,
  className = "",
  closeLabel = "Close dialog",
}: ModalProps) {
  const titleId = useId();
  const descriptionId = useId();
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const previousFocus = document.activeElement;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }

      if (event.key !== "Tab") return;
      const dialog = closeButtonRef.current?.closest('[role="dialog"]');
      const focusable = dialog?.querySelectorAll<HTMLElement>(
        'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
      if (previousFocus instanceof HTMLElement) previousFocus.focus();
    };
  }, []);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#061d36]/45 p-4 backdrop-blur-[2px]"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCloseRef.current();
      }}
    >
      <section
        aria-describedby={description ? descriptionId : undefined}
        aria-labelledby={titleId}
        aria-modal="true"
        className={`max-h-[min(90svh,760px)] w-[60%] overflow-y-auto rounded-xl border border-white/80 bg-[#f4f6f6] shadow-[0_16px_48px_rgba(0,20,40,0.32)] ${className}`}
        role="dialog"
      >
        <header className="sticky top-0 z-10 flex items-center justify-between bg-gradient-to-r from-[#00b9c5] to-[#0071b4] px-5 py-4 text-white">
          <div>
            <h2 className="text-xl font-bold" id={titleId}>{title}</h2>
            {description && <p className="mt-1 text-sm text-white/85" id={descriptionId}>{description}</p>}
          </div>
          <ButtonSecondary
            aria-label={closeLabel}
            className="!border-white/40 !bg-white/90 !text-[#173456] shadow-none hover:!bg-white focus-visible:ring-white"
            icon="close"
            iconOnly
            onClick={() => onCloseRef.current()}
            ref={closeButtonRef}
            type="button"
          />
        </header>
        <div className="p-5">
          {children}
          {footer && <div className="mt-4 flex justify-end gap-2 border-t border-[#dce5e9] pt-4">{footer}</div>}
        </div>
      </section>
    </div>,
    document.body,
  );
}