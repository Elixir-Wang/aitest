"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

import { X } from "lucide-react";
import { AnimatePresence, motion, type Transition } from "motion/react";

import { cn } from "@/lib/utils";

type HeadingData = {
  id: string;
  text: string;
  level: number;
  element: HTMLElement;
};

const islandTransition: Transition = {
  type: "tween",
  ease: [0.22, 1, 0.36, 1],
  duration: 0.5,
};
const SHOW_AFTER_SCROLL_Y = 80;

function CircleProgress({ percentage }: { percentage: number }) {
  const size = 24;
  const strokeWidth = 2.5;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <svg className="-rotate-90 shrink-0" height={size} width={size}>
      <circle
        cx={size / 2}
        cy={size / 2}
        fill="none"
        r={radius}
        stroke="var(--muted)"
        strokeWidth={strokeWidth}
      />
      <motion.circle
        animate={{ strokeDashoffset: offset }}
        cx={size / 2}
        cy={size / 2}
        fill="none"
        initial={{ strokeDashoffset: circumference }}
        r={radius}
        stroke="var(--foreground)"
        strokeDasharray={circumference}
        strokeLinecap="round"
        strokeWidth={strokeWidth}
        transition={{ duration: 0.15, ease: "easeOut" }}
      />
    </svg>
  );
}

type DynamicIslandTOCProps = {
  anchorSelector?: string;
  children?: ReactNode;
  refreshKey?: string | number;
  selector?: string;
};

export function DynamicIslandTOC({
  anchorSelector,
  children,
  refreshKey,
  selector = "article h1, article h2, article h3, article h4, .prose h1, .prose h2, .prose h3, .prose h4, [data-toc]",
}: DynamicIslandTOCProps) {
  const [headings, setHeadings] = useState<HeadingData[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [progress, setProgress] = useState(0);
  const [anchorCenter, setAnchorCenter] = useState<number | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const getHeadings = () => {
      const elements = Array.from(document.querySelectorAll(selector)) as HTMLElement[];

      const validHeadings = elements
        .filter((el) => !el.hasAttribute("data-toc-ignore"))
        .map((el, index) => {
          if (!el.id) {
            const generatedId =
              el.textContent
                ?.toLowerCase()
                .replace(/\s+/g, "-")
                .replace(/[^\w-]/g, "") || `toc-heading-${index}`;
            el.id = generatedId;
          }

          const depthAttr = el.getAttribute("data-toc-depth");
          let level = 2;

          if (depthAttr) {
            level = Number.parseInt(depthAttr, 10);
          } else {
            const tagName = el.tagName.toUpperCase();
            if (tagName.startsWith("H") && tagName.length === 2) {
              level = Number.parseInt(tagName[1], 10);
            }
          }

          const text = el.getAttribute("data-toc-title") || el.textContent || "Section";

          return { id: el.id, text, level, element: el };
        });

      validHeadings.sort((a, b) =>
        a.element.compareDocumentPosition(b.element) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
      );

      setHeadings(validHeadings);
    };

    const timer = window.setTimeout(getHeadings, 100);
    return () => window.clearTimeout(timer);
  }, [selector, refreshKey]);

  useEffect(() => {
    const handleScroll = () => {
      const hasScrollableHeadings = headings.length > 0;
      const shouldShow = window.scrollY > SHOW_AFTER_SCROLL_Y && hasScrollableHeadings;
      setIsVisible(shouldShow);
      if (!shouldShow) {
        setIsExpanded(false);
      }

      let currentActiveId: string | null = null;
      for (const heading of headings) {
        const top = heading.element.getBoundingClientRect().top;
        if (top <= 120) {
          currentActiveId = heading.id;
        } else {
          break;
        }
      }

      if (!currentActiveId && headings.length > 0) {
        currentActiveId = headings[0].id;
      }

      setActiveId(currentActiveId);

      const total = document.documentElement.scrollHeight - window.innerHeight;
      setProgress(total > 0 ? Math.min(100, Math.max(0, (window.scrollY / total) * 100)) : 0);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();

    return () => window.removeEventListener("scroll", handleScroll);
  }, [headings]);

  useEffect(() => {
    if (!anchorSelector) {
      setAnchorCenter(null);
      return;
    }

    const updateAnchorCenter = () => {
      const anchor = document.querySelector(anchorSelector);
      if (!(anchor instanceof HTMLElement)) {
        setAnchorCenter(null);
        return;
      }

      const rect = anchor.getBoundingClientRect();
      setAnchorCenter(rect.left + rect.width / 2);
    };

    const handleScroll = () => {
      updateAnchorCenter();
    };

    if (isVisible) {
      updateAnchorCenter();
    }

    window.addEventListener("resize", updateAnchorCenter);
    window.addEventListener("scroll", handleScroll, { passive: true });

    const observer = new ResizeObserver(updateAnchorCenter);
    const anchor = document.querySelector(anchorSelector);
    if (anchor instanceof HTMLElement) {
      observer.observe(anchor);
    }

    return () => {
      window.removeEventListener("resize", updateAnchorCenter);
      window.removeEventListener("scroll", handleScroll);
      observer.disconnect();
    };
  }, [anchorSelector, isVisible, refreshKey]);

  const activeHeading = headings.find((h) => h.id === activeId);

  const minLevel = useMemo(() => {
    if (headings.length === 0) {
      return 1;
    }
    return Math.min(...headings.map((h) => h.level));
  }, [headings]);

  return (
    <>
      {children}

      <AnimatePresence>
        {isExpanded ? (
          <motion.div
            animate={{ opacity: 1 }}
            className="fixed inset-0 z-[9998] bg-black/20 backdrop-blur-[4px]"
            exit={{ opacity: 0 }}
            initial={{ opacity: 0 }}
            onClick={() => setIsExpanded(false)}
            transition={islandTransition}
          />
        ) : null}
      </AnimatePresence>

      {isVisible ? (
        <motion.div
          animate={{ y: 0, opacity: 1 }}
          className="fixed bottom-[30px] z-[9999] flex -translate-x-1/2 flex-col items-center"
          initial={{ y: 50, opacity: 0 }}
          style={{ left: anchorCenter ?? "50%" }}
          transition={{ type: "spring", stiffness: 300, damping: 25 }}
        >
          <motion.div
            animate={{
              width: isExpanded ? 340 : 280,
              height: isExpanded ? 400 : 52,
              borderRadius: isExpanded ? 24 : 26,
            }}
            className="relative max-w-[calc(100vw-32px)] overflow-hidden border border-foreground/10 bg-background text-foreground shadow-2xl"
            initial={false}
            onClick={() => {
              if (!isExpanded) {
                setIsExpanded(true);
              }
            }}
            style={{ cursor: isExpanded ? "default" : "pointer" }}
            transition={islandTransition}
          >
            <motion.div
              animate={{
                opacity: isExpanded ? 0 : 1,
                scale: isExpanded ? 0.95 : 1,
                filter: isExpanded ? "blur(4px)" : "blur(0px)",
              }}
              className={cn(
                "absolute inset-0 flex items-center gap-4 px-4 sm:px-5",
                isExpanded && "pointer-events-none",
              )}
              initial={false}
              transition={{ ...islandTransition, delay: isExpanded ? 0 : 0.1 }}
            >
              <div className="h-2 w-2 shrink-0 rounded-full bg-foreground" />

              <div className="relative flex h-full flex-1 items-center overflow-hidden text-left">
                <AnimatePresence initial={false} mode="popLayout">
                  <motion.span
                    animate={{ opacity: 1, y: 0 }}
                    className="block w-full overflow-hidden text-ellipsis whitespace-nowrap font-medium text-foreground text-sm"
                    exit={{ opacity: 0, y: -15 }}
                    initial={{ opacity: 0, y: 15 }}
                    key={activeId || "empty"}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  >
                    {activeHeading?.text || "Contents"}
                  </motion.span>
                </AnimatePresence>
              </div>

              <CircleProgress percentage={progress} />
            </motion.div>

            <motion.div
            animate={{
              opacity: isExpanded ? 1 : 0,
              scale: isExpanded ? 1 : 1.05,
            }}
            className={cn("absolute inset-0 flex flex-col", !isExpanded && "pointer-events-none")}
            initial={false}
            transition={{ ...islandTransition, delay: isExpanded ? 0.1 : 0 }}
          >
            <div className="flex shrink-0 items-center justify-between px-6 pt-5 pb-3">
              <span className="font-semibold text-[11px] text-muted-foreground tracking-[0.08em]">TABLE OF CONTENTS</span>
              <button
                className="text-muted-foreground transition-colors hover:text-foreground"
                onClick={(e) => {
                  e.stopPropagation();
                  setIsExpanded(false);
                }}
                type="button"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto overscroll-contain px-3 pb-4" data-lenis-prevent="true">
              <div className="flex flex-col gap-0.5">
                {headings.map((h) => {
                  const isActive = activeId === h.id;
                  const isHovered = hoveredId === h.id;
                  const indentLevel = Math.max(0, h.level - minLevel);
                  const paddingLeft = indentLevel * 14 + 12;

                  return (
                    <button
                      className={cn(
                        "group flex w-full shrink-0 cursor-pointer items-center rounded-lg border-none py-2 pr-3 text-left text-sm transition-all duration-300 ease-out",
                        isActive && "bg-foreground/10 font-medium text-foreground",
                        !isActive && isHovered && "bg-foreground/5 text-foreground/85",
                        !isActive && !isHovered && "bg-transparent text-foreground/45",
                      )}
                      key={h.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        const yOffset = -80;
                        const y = h.element.getBoundingClientRect().top + window.scrollY + yOffset;
                        window.scrollTo({ top: y, behavior: "smooth" });
                        setIsExpanded(false);
                      }}
                      onMouseEnter={() => setHoveredId(h.id)}
                      onMouseLeave={() => setHoveredId(null)}
                      style={{ paddingLeft: `${paddingLeft}px` }}
                      type="button"
                    >
                      <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap transition-transform duration-300 group-hover:translate-x-1">
                        {h.text}
                      </span>

                      <motion.div
                        animate={{ scale: isActive ? 1 : 0, opacity: isActive ? 1 : 0 }}
                        className="ml-3 h-1.5 w-1.5 shrink-0 rounded-full bg-foreground"
                        initial={false}
                        transition={{ duration: 0.3, ease: "easeOut" }}
                      />
                    </button>
                  );
                })}
              </div>
            </div>
          </motion.div>
          </motion.div>
        </motion.div>
      ) : null}
    </>
  );
}
