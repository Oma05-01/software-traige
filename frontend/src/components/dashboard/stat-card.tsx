import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  description: string;
  icon: LucideIcon;
  accent: string;
  value: number | string;
}

export function StatCard({
  title,
  description,
  icon: Icon,
  accent,
  value,
}: StatCardProps) {
  return (
    <article className="rounded-2xl border border-[#e9edf3] bg-white p-5 shadow-[0_2px_8px_rgba(30,50,80,0.025)] transition-shadow hover:shadow-[0_6px_22px_rgba(30,50,80,0.06)]">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[12px] font-medium text-slate-500">
            {title}
          </p>

          <p className="mt-4 text-3xl font-semibold tracking-tight text-[#263750]">
            {value}
          </p>

          <p className="mt-2 text-[11px] text-slate-400">
            {description}
          </p>
        </div>

        <div
          className={`flex h-11 w-11 items-center justify-center rounded-xl ${accent}`}
        >
          <Icon size={20} strokeWidth={1.8} />
        </div>
      </div>
    </article>
  );
}