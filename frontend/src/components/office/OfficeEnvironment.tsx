"use client";

type PlantProps = {
  flip?: boolean;
};

function OfficePlant({ flip = false }: PlantProps) {
  return (
    <svg
      viewBox="0 0 84 124"
      className="h-full w-full drop-shadow-sm"
      aria-hidden="true"
      style={flip ? { transform: "scaleX(-1)" } : undefined}
    >
      <ellipse cx="42" cy="116" rx="31" ry="5" fill="#64748b" opacity=".16" />
      <g stroke="#527d68" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity=".8">
        <path d="M42 99 Q28 64 19 34" />
        <path d="M42 99 Q45 55 58 25" />
        <path d="M42 99 Q14 78 10 58" />
        <path d="M42 99 Q66 73 73 51" />
        <path d="M42 99 Q34 50 39 13" />
      </g>
      <g>
        <path d="M18 35 Q5 21 10 8 Q29 12 29 34 Q24 39 18 35Z" fill="#78a88a" />
        <path d="M58 27 Q56 7 72 3 Q77 23 62 33Z" fill="#5f9679" />
        <path d="M10 59 Q-1 42 5 32 Q23 41 20 62Z" fill="#91b99a" />
        <path d="M72 52 Q76 34 84 31 Q88 51 75 61Z" fill="#7cab89" />
        <path d="M39 17 Q32 2 43 -5 Q55 10 46 23Z" fill="#6e9f7e" />
      </g>
      <path d="M23 89 H61 L56 115 H28Z" fill="#b9a99a" />
      <path d="M20 86 Q42 81 64 86 L61 93 H23Z" fill="#d1c2b1" />
      <path d="M30 101 H55" stroke="#a99582" strokeWidth="1.5" opacity=".5" />
    </svg>
  );
}

/** Decorative room layer. Keep this behind the interactive agent stations. */
export function OfficeEnvironment() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 z-0 overflow-hidden"
    >
      {/* A broad frosted-glass window wall gives the room a sense of scale. */}
      <div className="absolute inset-x-[12%] top-0 h-[15%] overflow-hidden rounded-b-xl border-x border-b border-white/65 bg-white/20 shadow-[0_8px_24px_rgba(50,70,95,0.035)]">
        <div className="grid h-full grid-cols-4 gap-1.5 p-2 sm:gap-3 sm:p-3">
          {[0, 1, 2, 3].map((pane) => (
            <div
              key={pane}
              className="relative overflow-hidden rounded-b-md border-x border-b border-white/55 bg-gradient-to-b from-white/50 via-[#eaf2f8]/25 to-[#dce8f1]/10"
            >
              <div className="absolute -left-1/3 top-0 h-full w-1/2 rotate-[18deg] bg-white/20 blur-md" />
            </div>
          ))}
        </div>
        <div className="absolute inset-x-0 bottom-0 h-1 bg-white/55" />
      </div>

      {/* Soft daylight, deliberately low contrast behind the characters. */}
      <div className="absolute inset-x-0 top-0 h-[58%] bg-[radial-gradient(ellipse_at_50%_0%,rgba(255,255,255,0.42),transparent_68%)]" />
      <div className="absolute -left-[12%] top-[8%] h-[55%] w-[46%] -rotate-[18deg] bg-gradient-to-br from-white/20 to-transparent blur-2xl" />
      <div className="absolute -right-[12%] top-[8%] h-[55%] w-[46%] rotate-[18deg] bg-gradient-to-bl from-white/20 to-transparent blur-2xl" />

      {/* Central shared floor inset. */}
      <div className="absolute left-1/2 top-[54%] h-[54%] w-[42%] -translate-x-1/2 -translate-y-1/2 rounded-[44px] border border-white/45 bg-[#cbd6e2]/35 shadow-[inset_0_1px_8px_rgba(255,255,255,0.18)]" />

      {/* Plants sit in the side aisles on larger screens only. */}
      <div className="absolute bottom-[4%] left-[1.5%] hidden h-28 w-16 opacity-80 lg:block">
        <OfficePlant />
      </div>
      <div className="absolute bottom-[4%] right-[1.5%] hidden h-28 w-16 opacity-80 lg:block">
        <OfficePlant flip />
      </div>

      {/* Quiet floor reflections. */}
      <div className="absolute bottom-[3%] left-1/2 h-7 w-[58%] -translate-x-1/2 rounded-full bg-white/20 blur-xl" />
    </div>
  );
}
