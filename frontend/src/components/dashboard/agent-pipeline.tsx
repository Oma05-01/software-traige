import {
  ClipboardList,
  Search,
  MessageSquareText,
  ShieldCheck,
  Boxes,
  ArrowDown,
  GitBranch,
} from "lucide-react";

const sharedStages = [
  {
    number: "01",
    title: "Receptionist",
    description: "Classifies incoming tickets and assesses priority.",
    responsibility: "Classification",
    icon: ClipboardList,
  },
  {
    number: "04",
    title: "Support Rep",
    description: "Prepares a response using the investigation or product assessment.",
    responsibility: "Communication",
    icon: MessageSquareText,
  },
  {
    number: "05",
    title: "Human Review",
    description: "A staff member reviews proposals and authorizes actions.",
    responsibility: "Authorization",
    icon: ShieldCheck,
  },
];

const branches = [
  {
    number: "02A",
    title: "Debugger",
    description: "Investigates bug reports using technical documentation and evidence.",
    label: "Bug reports",
    icon: Search,
    accent: "bg-blue-50 text-blue-700",
  },
  {
    number: "02B",
    title: "Product Manager",
    description: "Assesses requested capabilities, scope and acceptance criteria.",
    label: "Feature requests",
    icon: Boxes,
    accent: "bg-violet-50 text-violet-700",
  },
];

export function AgentPipeline() {
  const ReceptionistIcon = sharedStages[0].icon;
  const SupportIcon = sharedStages[1].icon;
  const ReviewIcon = sharedStages[2].icon;

  return (
    <section className="rounded-2xl border border-[#e9edf3] bg-white p-5 shadow-[0_2px_8px_rgba(30,50,80,0.025)] sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-[#273750]">
            Multi-agent workflow
          </h2>

          <p className="mt-1 text-xs text-slate-400">
            Two processing paths with shared human oversight
          </p>
        </div>

        <span className="rounded-full bg-[#eef3f9] px-3 py-1.5 text-[10px] font-medium text-[#58749b]">
          Workflow architecture
        </span>
      </div>

      <div className="mt-6">
        <div className="rounded-xl border border-[#edf0f5] bg-[#fafbfd] p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#edf3fc]">
              <ReceptionistIcon size={19} className="text-[#6687b5]" />
            </div>

            <div>
              <p className="text-[10px] font-semibold tracking-wider text-slate-400">
                STAGE 01
              </p>
              <h3 className="mt-1 text-sm font-semibold text-[#2c3c54]">
                Receptionist
              </h3>
              <p className="mt-1 text-xs text-slate-500">
                Classifies incoming tickets and assesses priority.
              </p>
            </div>
          </div>
        </div>

        <div className="flex justify-center py-3">
          <ArrowDown size={17} className="text-slate-300" />
        </div>

        <div className="mb-3 flex items-center justify-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          <GitBranch size={14} />
          Category-based routing
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {branches.map((branch) => {
            const Icon = branch.icon;

            return (
              <article
                key={branch.number}
                className="rounded-xl border border-[#edf0f5] bg-[#fafbfd] p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-semibold tracking-wider text-slate-400">
                    STAGE {branch.number}
                  </span>

                  <span className={`rounded-full px-2 py-1 text-[9px] font-medium ${branch.accent}`}>
                    {branch.label}
                  </span>
                </div>

                <div className="mt-4 flex h-9 w-9 items-center justify-center rounded-xl bg-white">
                  <Icon size={19} className="text-[#6687b5]" />
                </div>

                <h3 className="mt-3 text-sm font-semibold text-[#2c3c54]">
                  {branch.title}
                </h3>

                <p className="mt-2 text-xs leading-5 text-slate-500">
                  {branch.description}
                </p>
              </article>
            );
          })}
        </div>

        <div className="flex justify-center py-3">
          <ArrowDown size={17} className="text-slate-300" />
        </div>

        <div className="space-y-3">
          <div className="rounded-xl border border-[#edf0f5] bg-[#fafbfd] p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f2effb]">
                <SupportIcon size={19} className="text-[#8574b4]" />
              </div>

              <div>
                <p className="text-[10px] font-semibold tracking-wider text-slate-400">
                  STAGE 03
                </p>
                <h3 className="mt-1 text-sm font-semibold text-[#2c3c54]">
                  Support Rep
                </h3>
                <p className="mt-1 text-xs text-slate-500">
                  Prepares a response for human review.
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-[#edf0f5] bg-[#fafbfd] p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#eaf7f1]">
                <ReviewIcon size={19} className="text-[#529b7a]" />
              </div>

              <div>
                <p className="text-[10px] font-semibold tracking-wider text-slate-400">
                  STAGE 04
                </p>
                <h3 className="mt-1 text-sm font-semibold text-[#2c3c54]">
                  Human Review
                </h3>
                <p className="mt-1 text-xs text-slate-500">
                  Reviews proposals and authorizes external actions.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}