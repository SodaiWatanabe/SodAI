"use client";

import { CircleAlert, Info, TriangleAlert, X } from "lucide-react";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export type ToastTone = "error" | "neutral" | "warning";

type ToastAction = {
  label: string;
  onClick: () => void | Promise<void>;
};

export type ToastInput = {
  action?: ToastAction;
  duration?: number | null;
  id: string;
  message: string;
  tone?: ToastTone;
};

type ToastRecord = Required<Pick<ToastInput, "id" | "message" | "tone">> &
  Pick<ToastInput, "action" | "duration">;

type ToastActions = {
  dismissToast: (id: string) => void;
  showToast: (toast: ToastInput) => void;
};

const ToastActionsContext = createContext<ToastActions | null>(null);
const ToastStateContext = createContext<ToastRecord[] | null>(null);
const DEFAULT_DURATION = 5000;
const MAX_VISIBLE_TOASTS = 3;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const timersRef = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const dismissToast = useCallback((id: string) => {
    const timer = timersRef.current.get(id);
    if (timer) clearTimeout(timer);
    timersRef.current.delete(id);
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback(
    (input: ToastInput) => {
      const toast: ToastRecord = {
        ...input,
        tone: input.tone ?? "neutral",
      };
      const existingTimer = timersRef.current.get(toast.id);
      if (existingTimer) clearTimeout(existingTimer);

      setToasts((current) => {
        const existingIndex = current.findIndex((item) => item.id === toast.id);
        if (existingIndex >= 0) {
          return current.map((item) => (item.id === toast.id ? toast : item));
        }
        return [...current, toast].slice(-MAX_VISIBLE_TOASTS);
      });

      const duration = toast.duration === undefined ? DEFAULT_DURATION : toast.duration;
      if (duration !== null) {
        timersRef.current.set(
          toast.id,
          setTimeout(() => dismissToast(toast.id), duration),
        );
      }
    },
    [dismissToast],
  );

  useEffect(
    () => () => {
      for (const timer of timersRef.current.values()) clearTimeout(timer);
      timersRef.current.clear();
    },
    [],
  );

  useEffect(() => {
    const visibleIds = new Set(toasts.map((toast) => toast.id));
    for (const [id, timer] of timersRef.current) {
      if (visibleIds.has(id)) continue;
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
  }, [toasts]);

  const actions = useMemo(
    () => ({ dismissToast, showToast }),
    [dismissToast, showToast],
  );

  return (
    <ToastActionsContext.Provider value={actions}>
      <ToastStateContext.Provider value={toasts}>{children}</ToastStateContext.Provider>
    </ToastActionsContext.Provider>
  );
}

export function ToastViewport() {
  const actions = useContext(ToastActionsContext);
  const toasts = useContext(ToastStateContext);
  if (!actions || !toasts) {
    throw new Error("ToastViewport must be used inside ToastProvider");
  }
  const { dismissToast } = actions;
  const icons = {
    error: CircleAlert,
    neutral: Info,
    warning: TriangleAlert,
  } as const;

  return (
    <div
      aria-label="通知"
      className="pointer-events-none absolute inset-x-0 top-14 z-20 flex flex-col items-center gap-2 px-4 sm:px-14 lg:top-2"
    >
      {toasts.map((toast) => {
        const Icon = icons[toast.tone];
        return (
          <div
            key={toast.id}
            role={toast.tone === "error" ? "alert" : "status"}
            className="toast-item pointer-events-auto flex w-full max-w-[420px] items-center gap-3 rounded-2xl border border-[var(--divider)] bg-[var(--surface-translucent)] px-3 py-2.5 text-[var(--text)] shadow-[0_14px_44px_var(--popover-shadow)] backdrop-blur-xl"
          >
            <Icon
              aria-hidden="true"
              className={`size-[17px] shrink-0 ${
                toast.tone === "error"
                  ? "text-[var(--danger-text)]"
                  : "text-[var(--muted)]"
              }`}
            />
            <p className="min-w-0 flex-1 text-[13px] leading-5">{toast.message}</p>
            {toast.action ? (
              <button
                type="button"
                className="shrink-0 rounded-lg px-2 py-1 text-[12px] font-semibold text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
                onClick={() => {
                  dismissToast(toast.id);
                  void toast.action?.onClick();
                }}
              >
                {toast.action.label}
              </button>
            ) : null}
            <button
              type="button"
              aria-label="通知を閉じる"
              className="grid size-7 shrink-0 place-items-center rounded-full text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
              onClick={() => dismissToast(toast.id)}
            >
              <X aria-hidden="true" className="size-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export function useToast() {
  const context = useContext(ToastActionsContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}
