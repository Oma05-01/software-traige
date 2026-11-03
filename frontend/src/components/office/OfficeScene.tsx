"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { AlertCircle, Check, Clock3 } from "lucide-react";

import type {
  OfficeAgent,
  OfficeAgentStatus as OfficeStatus,
} from "@/lib/types/office";
import type { AgentType } from "@/lib/types/workflow";

import { SeatedAgent } from "./SeatedAgent";

const ORDER: AgentType[] = [
  "receptionist",
  "debugger",
  "product_manager",
  "support_rep",
];

const META: Record<AgentType, { name: string; role: string }> = {
  receptionist: { name: "Receptionist", role: "Ticket intake" },
  debugger: { name: "Debugger", role: "Technical investigation" },
  product_manager: { name: "Product Manager", role: "Product assessment" },
  support_rep: { name: "Support Rep", role: "Communication" },
};

const STATUS: Record<OfficeStatus, { label: string; dot: string }> = {
  idle: { label: "Idle", dot: "bg-slate-300" },
  queued: { label: "Queued", dot: "bg-amber-400" },
  working: { label: "Working", dot: "bg-emerald-500" },
  completed: { label: "Completed", dot: "bg-blue-500" },
  failed: { label: "Failed", dot: "bg-red-500" },
};

const CARD_ACCENT: Record<OfficeStatus, string> = {
  idle: "border-l-slate-300",
  queued: "border-l-amber-400",
  working: "border-l-emerald-500",
  completed: "border-l-blue-500",
  failed: "border-l-red-500",
};

/**
 * Executions can finish between five-second office polls. When a new
 * execution first appears already finished, briefly replay its working
 * state so the activity remains visible to the person watching the office.
 */
function useDisplayStatus(agent: OfficeAgent, minMs = 1800): OfficeStatus {
  const execution = agent.current_execution ?? agent.latest_execution;
  const target = agent.status;

  const [shown, setShown] = useState<OfficeStatus>(target);
  const seenId = useRef(execution?.id ?? null);
  const since = useRef(0);

  useEffect(() => {
    const now = Date.now();
    const isNewExecution = Boolean(
      execution?.id && execution.id !== seenId.current,
    );

    seenId.current = execution?.id ?? null;

    if (isNewExecution) {
      since.current = now;

      const initialStatus: OfficeStatus =
        target === "completed" || target === "failed" ? "working" : target;

      const startTimer = window.setTimeout(() => {
        setShown(initialStatus);
      }, 0);

      const finishTimer = window.setTimeout(() => {
        setShown(target);
        since.current = Date.now();
      }, minMs);

      return () => {
        window.clearTimeout(startTimer);
        window.clearTimeout(finishTimer);
      };
    }

    const elapsed = now - since.current;
    const remaining = Math.max(0, minMs - elapsed);

    const timer = window.setTimeout(() => {
      setShown(target);
      since.current = Date.now();
    }, remaining);

    return () => window.clearTimeout(timer);
  }, [target, execution?.id, minMs]);

  return shown;
}

function Bubble({ status }: { status: OfficeStatus }) {
  return (
    <AnimatePresence mode="wait">
      {status !== "idle" && (
        <motion.div
          key={status}
          initial={{ opacity: 0, scale: 0.6, y: 6 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.8 }}
          transition={{ type: "spring", stiffness: 380, damping: 22 }}
          className="flex h-7 min-w-9 items-center justify-center rounded-full border border-slate-200 bg-white px-2.5 shadow-md"
          aria-label={`${STATUS[status].label} status`}
        >
          {status === "working" && (
            <span className="flex gap-1" aria-hidden="true">
              {[0, 1, 2].map((item) => (
                <motion.span
                  key={item}
                  className="h-1.5 w-1.5 rounded-full bg-emerald-500"
                  animate={{ y: [0, -3, 0] }}
                  transition={{
                    duration: 0.8,
                    repeat: Infinity,
                    delay: item * 0.15,
                  }}
                />
              ))}
            </span>
          )}
          {status === "queued" && (
            <Clock3 size={14} className="text-amber-500" />
          )}
          {status === "completed" && (
            <Check size={15} className="text-blue-600" />
          )}
          {status === "failed" && (
            <AlertCircle size={15} className="text-red-600" />
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Station({
  agent,
  mirror,
}: {
  agent: OfficeAgent;
  mirror: boolean;
}) {
  const shown = useDisplayStatus(agent);
  const execution = agent.current_execution ?? agent.latest_execution;
  const meta = META[agent.agent_type];
  const status = STATUS[shown];

  return (
    <div className="flex min-w-0 flex-col items-center">
      <div className="relative w-full max-w-[340px]">
        <div
          className="aspect-[300/230]"
          style={mirror ? { transform: "scaleX(-1)" } : undefined}
        >
          <SeatedAgent agentType={agent.agent_type} status={shown} />
        </div>

        <div
          className="pointer-events-none absolute top-[1%]"
          style={{
            left: mirror ? "71%" : "29%",
            transform: "translateX(-50%)",
          }}
        >
          <Bubble status={shown} />
        </div>
      </div>

      <div
        className={`-mt-1 w-full max-w-[340px] rounded-xl border border-white/80 border-l-[3px] bg-white/90 px-3 py-2.5 shadow-[0_4px_14px_rgba(36,55,80,0.07)] backdrop-blur-sm transition-colors ${CARD_ACCENT[shown]}`}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-[13px] font-semibold text-[#2c3c54]">
              {meta.name}
            </p>
            <p className="truncate text-[11px] text-slate-500">{meta.role}</p>
          </div>

          <span className="flex shrink-0 items-center gap-1.5 rounded-full bg-slate-50 px-2 py-1 text-[10px] font-medium text-slate-600">
            <span className={`h-2 w-2 rounded-full ${status.dot}`} />
            {status.label}
          </span>
        </div>

        <p className="mt-2 truncate border-t border-slate-100 pt-2 text-[11px] text-slate-500">
          {execution ? execution.ticket_title : "Waiting for an assignment"}
        </p>
      </div>
    </div>
  );
}

function OfficePlant({ right = false }: { right?: boolean }) {
  return (
    <svg
      viewBox="0 0 76 112"
      className="h-full w-full"
      aria-hidden="true"
      style={right ? { transform: "scaleX(-1)" } : undefined}
    >
      <ellipse cx="38" cy="104" rx="30" ry="5" fill="#536477" opacity=".12" />

      {/* Leaves */}
      <path d="M38 82 Q8 65 15 38 Q37 43 38 82" fill="#6d9c83" />
      <path d="M38 79 Q61 54 55 29 Q35 43 38 79" fill="#83af91" />
      <path d="M38 72 Q18 42 31 17 Q47 39 38 72" fill="#527f6b" />
      <path d="M39 78 Q48 43 66 41 Q66 66 39 78" fill="#97b99a" />
      <path d="M37 87 Q3 83 8 61 Q31 61 37 87" fill="#729c7c" />

      {/* Pot */}
      <path d="M21 82 H55 L50 105 H26 Z" fill="#b9a99a" />
      <rect x="19" y="81" width="38" height="6" rx="2" fill="#d0c2b2" />
      <path d="M27 91 H49" stroke="#aa9887" opacity=".6" />
    </svg>
  );
}

/** Decorative room details, kept in this file to avoid a duplicate import. */
function OfficeEnvironment() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 z-0 overflow-hidden"
    >
      {/* Glass window panels */}
      <div className="absolute inset-x-[10%] top-0 h-[13%] rounded-b-xl border-x border-b border-white/60 bg-white/20">
        <div className="grid h-full grid-cols-3 gap-2 p-2">
          {[0, 1, 2].map((item) => (
            <div
              key={item}
              className="rounded-b-lg border-x border-b border-white/50 bg-gradient-to-b from-white/35 to-white/5"
            />
          ))}
        </div>
      </div>

      {/* Soft daylight */}
      <div className="absolute inset-x-0 top-0 h-[45%] bg-gradient-to-b from-white/30 to-transparent" />

      {/* Central collaboration area */}
      <div className="absolute left-1/2 top-[53%] h-[59%] w-[40%] -translate-x-1/2 -translate-y-1/2 rounded-[48%] border border-white/50 bg-[#cbd6e2]/40 shadow-inner" />

      {/* Floor reflections */}
      <div className="absolute bottom-[7%] left-[20%] h-8 w-[60%] rounded-full bg-white/15 blur-xl" />

      {/* Indoor plants */}
      <div className="absolute bottom-3 left-3 hidden h-24 w-16 sm:block">
        <OfficePlant />
      </div>
      <div className="absolute bottom-3 right-3 hidden h-24 w-16 sm:block">
        <OfficePlant right />
      </div>
    </div>
  );
}

export function OfficeScene({ agents }: { agents: OfficeAgent[] }) {
  const ordered = ORDER.map((type) => {
    const existing = agents.find((agent) => agent.agent_type === type);

    if (existing) return existing;

    return {
      agent_type: type,
      status: "idle" as OfficeStatus,
      active_count: 0,
      current_execution: null,
      latest_execution: null,
    };
  });

  return (
    <MotionConfig reducedMotion="user">
      <div
        className="relative overflow-hidden"
        style={{
          background: `
            repeating-linear-gradient(
              90deg,
              transparent 0 79px,
              rgba(40,60,90,.045) 79px 80px
            ),
            repeating-linear-gradient(
              0deg,
              transparent 0 79px,
              rgba(40,60,90,.025) 79px 80px
            ),
            linear-gradient(180deg, #eef2f6 0%, #dce4ec 100%)
          `,
        }}
      >
        <OfficeEnvironment />

        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 z-[1]"
          style={{
            background:
              "linear-gradient(115deg, rgba(255,255,255,.4), transparent 45%)",
          }}
        />

        <div className="relative z-10 grid grid-cols-1 gap-x-4 gap-y-8 px-4 py-6 sm:grid-cols-2 sm:gap-x-10 sm:gap-y-7 sm:px-8 sm:py-8">
          {ordered.map((agent, index) => (
            <Station
              key={agent.agent_type}
              agent={agent}
              mirror={index % 2 === 1}
            />
          ))}
        </div>
      </div>
    </MotionConfig>
  );
}
