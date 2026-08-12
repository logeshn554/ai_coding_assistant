import React, {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

/* ─────────────────────────────────────────────────────────
 * SELECTION ACTIONS (Inline Suggestion / Contextual AI Bar)
 * A contextual AI bar attached beneath selected text.
 * Composes surface, ink, accent, radius and motion tokens.
 * ───────────────────────────────────────────────────────── */

const LEAD = "Pistachio holds the top slot all weekend. ";
const PICKED =
  "Churn it first thing Saturday so the batch has time to firm up before the afternoon rush.";
const REWRITE =
  "Churn pistachio first thing Saturday so the batch has time to fully firm before the afternoon rush.";

type Mode = "idle" | "thinking" | "streaming" | "result";

function StreamText({
  text,
  onProgress,
  onDone,
}: {
  text: string;
  onProgress?: () => void;
  onDone?: () => void;
}) {
  const [displayed, setDisplayed] = useState("");
  useEffect(() => {
    let index = 0;
    const timer = setInterval(() => {
      index += 1;
      setDisplayed(text.slice(0, index));
      if (onProgress) onProgress();
      if (index >= text.length) {
        clearInterval(timer);
        if (onDone) onDone();
      }
    }, 28);
    return () => clearInterval(timer);
  }, [text, onProgress, onDone]);

  return <span>{displayed}</span>;
}

function Shimmer({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`bg-clip-text text-transparent ${className}`}
      style={{
        backgroundImage:
          "linear-gradient(90deg, var(--ink-3) 35%, var(--ink) 50%, var(--ink-3) 65%)",
        backgroundSize: "200% 100%",
        animation: "shimmer-text 1.4s linear infinite",
      }}
    >
      {children}
    </span>
  );
}

const icons = {
  explain: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <path d="M12 8v4M12 16h.01" />
    </svg>
  ),
  improve: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z" />
    </svg>
  ),
  shorten: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="6" cy="6" r="3" />
      <circle cx="6" cy="18" r="3" />
      <path d="M20 4L8.12 15.88M14.47 14.48L20 20M8.12 8.12L12 12" />
    </svg>
  ),
  tone: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <path d="M8 14s1.5 2 4 2 4-2 4-2M9 9h.01M15 9h.01" />
    </svg>
  ),
  grammar: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 7h16M4 12h16M4 17h10" />
    </svg>
  ),
  send: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 19V5M5 12l7-7 7 7" />
    </svg>
  ),
  chevron: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 18l6-6-6-6" />
    </svg>
  ),
  check: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 6L9 17l-5-5" />
    </svg>
  ),
  close: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  ),
  retry: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M23 4v6h-6M1 20v-6h6" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  ),
};

const control =
  "inline-flex h-7 shrink-0 items-center gap-1 rounded-full px-2.5 text-[12px] font-normal text-ink transition-[background-color,color,transform] duration-150 hover:bg-hover active:scale-[0.96] cursor-pointer focus:outline-none";

const primary =
  "inline-flex h-7 shrink-0 items-center gap-1 rounded-full bg-ink px-2.5 text-[12.5px] font-normal text-canvas shadow-hairline transition-[opacity,transform] duration-150 hover:opacity-90 active:scale-[0.96] cursor-pointer focus:outline-none";

export interface SelectionActionsProps {
  leadText?: string;
  pickedText?: string;
  rewriteText?: string;
}

export default function SelectionActions({
  leadText = LEAD,
  pickedText = PICKED,
  rewriteText = REWRITE,
}: SelectionActionsProps) {
  const [shown, setShown] = useState(false);
  const [mode, setMode] = useState<Mode>("idle");
  const [action, setAction] = useState("Improve");
  const [prompt, setPrompt] = useState("");
  const [typingWidth, setTypingWidth] = useState<number | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [anchor, setAnchor] = useState({ x: 0, y: 0 });
  const [positioned, setPositioned] = useState(false);

  const hostRef = useRef<HTMLDivElement>(null);
  const selectionRef = useRef<HTMLSpanElement>(null);
  const barRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<number | null>(null);
  const previousModeRef = useRef<Mode>("idle");
  const lastWidthRef = useRef(0);
  const widthAnimationRef = useRef<Animation | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setShown(true), 280);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (mode !== "thinking") return;
    const timer = window.setTimeout(() => setMode("streaming"), 700);
    return () => window.clearTimeout(timer);
  }, [mode]);

  /* Attach beneath the final selected line, while centering the bar
   * against the complete selection bounds. requestAnimationFrame batches
   * streaming reflow measurements and avoids visible intermediate positions. */
  const place = useCallback(() => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    frameRef.current = requestAnimationFrame(() => {
      const host = hostRef.current;
      const selection = selectionRef.current;
      if (!host || !selection) return;

      const bounds = selection.getBoundingClientRect();
      const lines = Array.from(selection.getClientRects());
      const lastLine = lines.at(-1);
      if (!lastLine) return;

      const hostBounds = host.getBoundingClientRect();
      const next = {
        x: Math.round(bounds.left - hostBounds.left + bounds.width / 2),
        y: Math.round(lastLine.bottom - hostBounds.top + 8),
      };

      setAnchor((current) =>
        current.x === next.x && current.y === next.y ? current : next,
      );
      setPositioned(true);
    });
  }, []);

  useLayoutEffect(() => {
    place();
  }, [mode, place]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const observer = new ResizeObserver(place);
    observer.observe(host);
    window.addEventListener("resize", place);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", place);
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    };
  }, [place]);

  /* Intrinsic width handles the preset expansion. When the entire content
   * changes between idle, loading and confirmation, animate from the last
   * rendered width to the new intrinsic width before the browser paints. */
  useLayoutEffect(() => {
    const bar = barRef.current;
    const content = contentRef.current;
    if (!bar || !content) return;

    const nextWidth = Math.ceil(content.getBoundingClientRect().width) + 8;
    const previousWidth =
      lastWidthRef.current || Math.ceil(bar.getBoundingClientRect().width);

    if (
      previousModeRef.current !== mode &&
      Math.abs(nextWidth - previousWidth) > 1
    ) {
      widthAnimationRef.current?.cancel();
      const animation = bar.animate(
        [
          { width: `${previousWidth}px` },
          { width: `${nextWidth}px` },
        ],
        {
          duration: 320,
          easing: "cubic-bezier(0.23,1,0.32,1)",
        },
      );
      widthAnimationRef.current = animation;
      animation.onfinish = () => {
        lastWidthRef.current = nextWidth;
        widthAnimationRef.current = null;
      };
    } else {
      lastWidthRef.current = nextWidth;
    }

    previousModeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    const content = contentRef.current;
    if (!content) return;

    const observer = new ResizeObserver(() => {
      if (widthAnimationRef.current?.playState === "running") return;
      lastWidthRef.current =
        Math.ceil(content.getBoundingClientRect().width) + 8;
    });
    observer.observe(content);
    return () => {
      observer.disconnect();
      widthAnimationRef.current?.cancel();
    };
  }, []);

  const run = (nextAction: string) => {
    setAction(nextAction);
    setExpanded(false);
    setMode("thinking");
  };

  const reset = () => {
    setExpanded(false);
    setPrompt("");
    setTypingWidth(null);
    setAction("Improve");
    setMode("idle");
  };

  const busy = mode === "thinking" || mode === "streaming";
  const visible = shown && positioned;
  const hasPrompt = prompt.trim().length > 0;
  const busyLabel =
    action === "Improve"
      ? "Improving"
      : action === "Shorten"
      ? "Shortening"
      : action === "Change tone"
      ? "Changing tone"
      : "Editing";

  return (
    <div className="w-full max-w-[460px] font-sans">
      <div ref={hostRef} className="relative select-none pb-12">
        <p className="text-[13px] leading-relaxed text-ink">
          {leadText}
          <span
            ref={selectionRef}
            className="box-decoration-clone rounded-[3px] bg-[color-mix(in_srgb,var(--accent)_14%,var(--surface))] text-ink dark:bg-accent-tint"
          >
            {mode === "idle" || mode === "thinking" ? (
              pickedText
            ) : mode === "streaming" ? (
              <StreamText
                text={rewriteText}
                onProgress={place}
                onDone={() => setMode("result")}
              />
            ) : (
              rewriteText
            )}
          </span>
        </p>

        <div
          className="absolute top-0 left-0 z-10"
          style={{
            transform: `translate3d(${anchor.x}px, ${anchor.y}px, 0) translateX(-50%)`,
            transition:
              "transform 320ms cubic-bezier(0.77,0,0.175,1), opacity 180ms ease-out",
            opacity: visible ? 1 : 0,
            pointerEvents: visible ? "auto" : "none",
            willChange: "transform",
          }}
        >
          {/* A 36px pill wraps 28px controls at a 4px inset. The controls
              resolve to a 14px radius, preserving the concentric curve. */}
          <div
            ref={barRef}
            className="flex h-9 w-fit max-w-[calc(100vw-48px)] items-center justify-center gap-0.5 overflow-hidden rounded-full bg-surface p-1 font-sans font-normal text-ink antialiased shadow-overlay border border-line"
            style={{
              width:
                mode === "idle" && hasPrompt && typingWidth
                  ? typingWidth
                  : undefined,
              ...(visible
                ? {
                    animation:
                      "pop-in 220ms cubic-bezier(0.23,1,0.32,1) both",
                  }
                : {}),
            }}
          >
            <div
              ref={contentRef}
              className="flex w-fit shrink-0 items-center justify-center gap-0.5"
              style={{
                width:
                  mode === "idle" && hasPrompt && typingWidth
                    ? typingWidth - 8
                    : undefined,
              }}
            >
              {busy && (
                <span className="inline-flex h-7 items-center gap-1.5 whitespace-nowrap px-2.5 text-[12.5px] font-normal text-ink-2">
                  <span
                    className="size-3 shrink-0 rounded-full border-[1.5px] border-line-strong border-t-ink-2"
                    style={{ animation: "spin 700ms linear infinite" }}
                  />
                  {mode === "thinking" ? (
                    <Shimmer className="text-[12.5px] font-normal">
                      {busyLabel}…
                    </Shimmer>
                  ) : (
                    <span>{busyLabel}…</span>
                  )}
                </span>
              )}

              {mode === "result" && (
                <>
                  <button type="button" onClick={reset} className={primary}>
                    {icons.check}
                    Keep
                  </button>
                  <button type="button" onClick={reset} className={control}>
                    {icons.close}
                    Discard
                  </button>
                  <span className="mx-0.5 h-4 w-px shrink-0 bg-line" />
                  <button
                    type="button"
                    aria-label="Try again"
                    onClick={() => run(action)}
                    className="flex size-7 shrink-0 items-center justify-center rounded-full text-ink-3 transition-[background-color,color,transform] duration-150 hover:bg-hover-2 hover:text-ink-2 active:scale-[0.96] cursor-pointer focus:outline-none"
                  >
                    {icons.retry}
                  </button>
                </>
              )}

              {mode === "idle" && (
                <>
                  <div
                    className="flex min-w-0 items-center overflow-hidden transition-[max-width,opacity,transform] duration-400"
                    style={{
                      maxWidth: expanded
                        ? 0
                        : hasPrompt && typingWidth
                        ? typingWidth - 40
                        : 145,
                      opacity: expanded ? 0 : 1,
                      transform: expanded ? "translateX(-8px)" : "translateX(0)",
                      transitionTimingFunction: "cubic-bezier(0.23,1,0.32,1)",
                    }}
                  >
                    <form
                      className="flex h-7 shrink-0 items-center transition-[width] duration-400"
                      style={{
                        width:
                          hasPrompt && typingWidth ? typingWidth - 40 : 145,
                        transitionTimingFunction: "cubic-bezier(0.23,1,0.32,1)",
                      }}
                      onSubmit={(event) => {
                        event.preventDefault();
                        run(prompt.trim() || "Improve");
                      }}
                    >
                      <input
                        value={prompt}
                        onChange={(event) => {
                          const next = event.target.value;
                          if (!prompt.trim() && next.trim()) {
                            setTypingWidth(
                              Math.ceil(
                                barRef.current?.getBoundingClientRect().width ??
                                  0,
                              ),
                            );
                          } else if (!next.trim()) {
                            setTypingWidth(null);
                          }
                          setPrompt(next);
                        }}
                        aria-label="Describe edits"
                        placeholder="Describe edits"
                        className="h-7 w-full bg-transparent pr-2.5 pl-3 text-[12.5px] text-ink placeholder:text-ink-3 outline-none"
                      />
                    </form>
                  </div>

                  <div
                    className="flex min-w-0 items-center gap-0.5 overflow-hidden transition-[max-width,opacity,transform] duration-400"
                    style={{
                      maxWidth: hasPrompt ? 0 : expanded ? 462 : 224,
                      opacity: hasPrompt ? 0 : 1,
                      transform: hasPrompt
                        ? "translateX(-8px)"
                        : "translateX(0)",
                      transitionTimingFunction: "cubic-bezier(0.23,1,0.32,1)",
                    }}
                  >
                    {!expanded && (
                      <span className="mx-1 h-4 w-px shrink-0 bg-line-strong" />
                    )}
                    <button
                      type="button"
                      onClick={() => run("Explain")}
                      className={control}
                    >
                      {icons.explain}
                      Explain
                    </button>
                    <button
                      type="button"
                      onClick={() => run("Improve")}
                      className={control}
                    >
                      {icons.improve}
                      Improve
                    </button>

                    <div
                      className="flex min-w-0 items-center gap-0.5 overflow-hidden transition-[max-width,opacity,margin] duration-400"
                      style={{
                        maxWidth: expanded ? 262 : 0,
                        opacity: expanded ? 1 : 0,
                        marginLeft: expanded ? 2 : 0,
                        transitionTimingFunction: "cubic-bezier(0.23,1,0.32,1)",
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => run("Shorten")}
                        className={control}
                      >
                        {icons.shorten}
                        Shorten
                      </button>
                      <button
                        type="button"
                        onClick={() => run("Change tone")}
                        className={control}
                      >
                        {icons.tone}
                        Tone
                      </button>
                      <button
                        type="button"
                        onClick={() => run("Fix grammar")}
                        className={control}
                      >
                        {icons.grammar}
                        Grammar
                      </button>
                    </div>

                    <span className="mx-0.5 h-4 w-px shrink-0 bg-line" />
                    <button
                      type="button"
                      aria-label={
                        expanded ? "Show fewer actions" : "Show more actions"
                      }
                      aria-expanded={expanded}
                      onClick={() => setExpanded((value) => !value)}
                      className="flex size-7 shrink-0 items-center justify-center rounded-full text-ink transition-[background-color,transform] duration-200 hover:bg-hover active:scale-[0.96] cursor-pointer focus:outline-none"
                    >
                      <span
                        className="flex transition-transform duration-400"
                        style={{
                          transform: expanded
                            ? "rotate(180deg)"
                            : "rotate(0deg)",
                          transitionTimingFunction:
                            "cubic-bezier(0.23,1,0.32,1)",
                        }}
                      >
                        {icons.chevron}
                      </span>
                    </button>
                  </div>

                  <div
                    className="flex min-w-0 items-center overflow-hidden transition-[max-width,opacity,transform] duration-400"
                    style={{
                      maxWidth: hasPrompt ? 30 : 0,
                      opacity: hasPrompt ? 1 : 0,
                      transform: hasPrompt ? "scale(1)" : "scale(0.88)",
                      transitionTimingFunction: "cubic-bezier(0.23,1,0.32,1)",
                    }}
                  >
                    <button
                      type="button"
                      aria-label="Send edit instruction"
                      onClick={() => run(prompt.trim())}
                      className="flex size-7 shrink-0 items-center justify-center rounded-full bg-ink text-canvas transition-[opacity,transform] duration-200 active:scale-[0.94] cursor-pointer focus:outline-none"
                    >
                      {icons.send}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
