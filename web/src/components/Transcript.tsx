import { useEffect, useRef } from "react";
import type { Turn } from "../data";

export interface TurnMark { flagged?: string[]; planted?: string; near?: string }

/** A conversation as message bubbles: customer on the left, agent on the
 * right, tool actions centred. Flagged and planted turns are marked with a
 * ring or a dashed outline plus a text tag, never colour alone. */
export function Transcript({ turns, marks, active }: { turns: Turn[]; marks: Record<number, TurnMark>; active?: number }) {
  const refs = useRef<Record<number, HTMLDivElement | null>>({});
  useEffect(() => {
    if (active !== undefined) refs.current[active]?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [active]);

  return (
    <div className="transcript" aria-label="Transcript">
      {turns.map((t) => {
        const m = marks[t.idx] ?? {};
        const cls = ["turn", t.speaker, m.flagged?.length ? "flagged" : "", m.planted ? "planted" : "",
          active === t.idx ? "active" : ""].join(" ");
        return (
          <div key={t.idx} className={cls} ref={(el) => { refs.current[t.idx] = el; }} id={`turn-${t.idx}`}>
            <div className="turn-meta">#{t.idx}{t.start ? ` · ${t.start}` : ""} · {t.speaker}</div>
            <div className="bubble">{t.text}</div>
            {(m.flagged?.length || m.planted || m.near) && (
              <div className="turn-tags">
                {m.planted && <span className="pill st-planted">planted: {m.planted}</span>}
                {m.near && <span className="pill st-near">near-miss: {m.near}</span>}
                {m.flagged?.map((c) => <span key={c} className="pill sev-major">flagged: {c}</span>)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
