"use client";

/**
 * Tooltip educativo (§16 do contrato do agente). Acessível: abre no hover e no
 * foco por teclado; o texto também vai no aria-label.
 */
export default function InfoTip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex align-middle">
      <button
        type="button"
        aria-label={text}
        className="grid h-4 w-4 cursor-help place-items-center rounded-full border border-border text-[9px] font-bold text-muted-foreground transition hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
      >
        i
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 hidden w-56 -translate-x-1/2 rounded-lg border border-border bg-surface p-3 text-[11px] font-normal normal-case leading-relaxed tracking-normal text-foreground shadow-lg group-hover:block group-focus-within:block"
      >
        {text}
      </span>
    </span>
  );
}
