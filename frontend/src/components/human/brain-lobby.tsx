import { BrainSpaceBackground } from "@/components/human/brain-space-background";
import { BrainWaitingGuide } from "@/components/human/brain-waiting-guide";

type BrainLobbyMode = "signed-out" | "idle" | "waiting";

type BrainLobbyProps = {
  busy?: boolean;
  error?: string;
  mode: BrainLobbyMode;
  notice?: string;
  onAction: () => void;
};

const actionLabel = {
  "signed-out": "ログイン",
  idle: "思考を始める",
  waiting: "待機をやめる",
} satisfies Record<BrainLobbyMode, string>;

type LobbyActionButtonProps = {
  active?: boolean;
  busy: boolean;
  mode: BrainLobbyMode;
  onAction: () => void;
};

function LobbyActionButton({
  active = true,
  busy,
  mode,
  onAction,
}: LobbyActionButtonProps) {
  const waiting = mode === "waiting";

  return (
    <button
      type="button"
      aria-busy={active && busy}
      disabled={!active || busy}
      className={`h-10 rounded-full px-5 text-sm font-medium transition-colors disabled:cursor-default disabled:opacity-50 ${
        waiting
          ? "mt-3 border border-[light-dark(var(--border),transparent)] bg-[var(--button-background)] text-[var(--text)] backdrop-blur-md hover:bg-[var(--button-hover)]"
          : "bg-[var(--primary)] text-[var(--on-primary)] hover:bg-[var(--primary-hover)]"
      } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]`}
      onClick={onAction}
    >
      {actionLabel[mode]}
    </button>
  );
}

export function BrainLobby({
  busy = false,
  error,
  mode,
  notice,
  onAction,
}: BrainLobbyProps) {
  const waiting = mode === "waiting";

  return (
    <section className="relative isolate grid flex-1 place-items-center overflow-hidden px-6">
      <BrainSpaceBackground />

      <div className="relative z-10 w-full max-w-md text-center">
        {mode === "signed-out" ? (
          <LobbyActionButton
            busy={busy}
            mode="signed-out"
            onAction={onAction}
          />
        ) : (
          <div className="relative h-[156px] sm:h-[164px]">
            <div
              aria-hidden={waiting}
              className={`absolute inset-0 grid place-items-center transition-[opacity,filter] duration-1000 ease-in-out motion-reduce:transition-none ${
                waiting
                  ? "pointer-events-none z-0 opacity-0 blur-md"
                  : "z-10 opacity-100 blur-0"
              }`}
            >
              <LobbyActionButton
                active={!waiting}
                busy={busy}
                mode="idle"
                onAction={onAction}
              />
            </div>

            <div
              aria-hidden={!waiting}
              className={`absolute inset-0 transition-[opacity,filter] duration-1000 ease-in-out motion-reduce:transition-none ${
                waiting
                  ? "z-10 opacity-100 blur-0"
                  : "pointer-events-none z-0 opacity-0 blur-md"
              }`}
            >
              <BrainWaitingGuide active={waiting} />
              <LobbyActionButton
                active={waiting}
                busy={busy}
                mode="waiting"
                onAction={onAction}
              />
            </div>
          </div>
        )}

        {error ? (
          <p role="alert" className="mt-4 text-xs text-[var(--danger-text)]">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p role="status" className="mt-4 text-xs text-[var(--muted)]">
            {notice}
          </p>
        ) : null}
      </div>
    </section>
  );
}
