import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import ButtonSecondary from "../components/ButtonSecondary";
import Icon from "../components/Icon";
import { ToastContext, type ToastKind } from "./toastContextValue";

type Toast = { id: number; message: string; kind: ToastKind; expiresAt: number };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);
  const showToast = useCallback((message: string, kind: ToastKind = "info") => {
    const id = ++nextId.current;
    setToasts((current) => [...current, { id, message, kind, expiresAt: Date.now() + 5000 }]);
  }, []);

  useEffect(() => {
    const timers = toasts.map(({ id, expiresAt }) =>
      window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), Math.max(0, expiresAt - Date.now())),
    );
    return () => timers.forEach(window.clearTimeout);
  }, [toasts]);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed left-1/2 top-4 -translate-x-1/2 z-[100] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2">
        {toasts.map(({ id, message, kind }) => (
          <div
            className={`pointer-events-auto flex items-start gap-3 rounded-xl border bg-white px-4 py-3 shadow-[0_8px_24px_rgba(8,38,76,0.2)] ${
              kind === "success" ? "border-[#9ad9c0]" : kind === "error" ? "border-[#f2b7b7]" : "border-[#b8dce4]"
            }`}
            key={id}
            role={kind === "error" ? "alert" : "status"}
          >
            <Icon
              className={`mt-0.5 h-5 w-5 shrink-0 ${kind === "success" ? "text-emerald-700" : kind === "error" ? "text-red-700" : "text-cyan-800"}`}
              name={kind === "success" ? "check" : kind === "error" ? "close" : "activity"}
            />
            <p className="min-w-0 flex-1 text-sm leading-5 text-[#173456]">{message}</p>
            <ButtonSecondary
              aria-label="Dismiss notification"
              className="h-7 w-7 shrink-0 border-0 bg-transparent p-0 shadow-none"
              icon="close"
              iconOnly
              onClick={() => setToasts((current) => current.filter((toast) => toast.id !== id))}
              type="button"
            />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
