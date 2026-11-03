"use client";

import { motion } from "motion/react";

import type { OfficeAgentStatus as S } from "@/lib/types/office";
import type { AgentType } from "@/lib/types/workflow";

type Look = {
  shirt: string;
  skin: string;
  hair: string;
  accent: string;
  style: "long" | "short" | "curly" | "coils";
};

const LOOKS: Record<AgentType, Look> = {
  receptionist: {
    shirt: "#3f9bf0",
    skin: "#e9b690",
    hair: "#c95628",
    accent: "#8bc7ff",
    style: "long",
  },
  debugger: {
    shirt: "#278d7d",
    skin: "#bd805b",
    hair: "#202633",
    accent: "#69dfbd",
    style: "short",
  },
  product_manager: {
    shirt: "#896cce",
    skin: "#f0c39e",
    hair: "#563526",
    accent: "#c7b2ff",
    style: "curly",
  },
  support_rep: {
    shirt: "#e99a43",
    skin: "#a66e4c",
    hair: "#261d1a",
    accent: "#ffd08a",
    style: "coils",
  },
};

const BLINK_DELAY: Record<AgentType, number> = {
  receptionist: 0,
  debugger: 1.3,
  product_manager: 2.1,
  support_rep: 0.7,
};

const loop = { repeat: Infinity, ease: "easeInOut" as const };

const FACE_SHAPES: Record<AgentType, string> = {
  receptionist:
    "M71 46 Q76 36 89 38 Q103 40 105 55 L104 67 Q101 81 88 82 Q75 81 71 69 Q68 58 71 46Z",
  debugger:
    "M72 45 Q79 36 92 39 Q105 42 105 57 L101 70 Q97 81 85 79 Q74 76 72 64 Q69 54 72 45Z",
  product_manager:
    "M70 47 Q76 37 89 38 Q103 39 105 54 L104 66 Q101 81 88 83 Q75 81 71 68 Q68 58 70 47Z",
  support_rep:
    "M71 46 Q77 37 91 39 Q105 42 105 57 L102 70 Q98 81 85 80 Q74 78 71 66 Q68 56 71 46Z",
};

const HAIR_BACK: Record<Look["style"], string> = {
  long: "M68 64 C60 47 65 33 82 31 C100 29 111 43 108 62 L108 91 Q100 99 91 87 L89 72 L79 88 Q68 86 66 75Z",
  short: "M68 62 C63 45 73 33 89 34 C105 35 111 47 106 64 L100 76 L95 65 L78 76 L72 70Z",
  curly: "M67 62 C61 47 68 32 83 32 C101 29 112 44 108 63 L103 75 L96 67 L77 77 L70 70Z",
  coils: "M68 63 C61 47 68 34 83 32 C99 30 111 43 108 62 L105 76 L98 72 L94 83 L84 76 L76 81 L70 72Z",
};

const HAIR_CAP: Record<Look["style"], string> = {
  long: "M68 59 C65 42 77 34 91 37 C103 39 109 49 105 61 L99 56 Q90 47 82 55 L74 67Z",
  short: "M68 58 C66 42 78 35 91 37 C102 39 108 48 105 60 L99 55 Q91 49 83 53 L76 63 L72 66Z",
  curly: "M67 59 C65 43 78 34 91 37 C104 39 110 49 105 61 L99 55 Q91 49 83 54 L76 65 L72 66Z",
  coils: "M68 59 C66 43 78 34 91 37 C104 39 110 49 105 61 L99 55 Q91 49 83 54 L76 65 L72 66Z",
};

function armPose(status: S, far: boolean, agentType: AgentType) {
  const amplitude = far ? 0.68 : 1;

  if (status === "working") {
    const rhythm: Record<AgentType, number[]> = {
      receptionist: [0, -5, 2, -4, 0],
      debugger: [0, -8, 3, -6, 1, 0],
      product_manager: [0, -3, 5, -2, 4, 0],
      support_rep: [0, -6, 1, -8, 2, 0],
    };
    const values = rhythm[agentType];

    return {
      upper: {
        rotate:
          agentType === "debugger"
            ? [0, 2.2 * amplitude, -1.5 * amplitude, 0]
            : [0, 1.5 * amplitude, -1 * amplitude, 0],
        transition: { duration: agentType === "support_rep" ? 1.9 : 1.6, ...loop },
      },
      fore: {
        rotate: values.map((value) => value * amplitude),
        transition: {
          duration:
            agentType === "product_manager"
              ? 1.8
              : agentType === "debugger"
                ? 1.05
                : 1.3,
          times: values.map((_, index) => index / (values.length - 1)),
          ...loop,
        },
      },
    };
  }

  if (status === "queued") {
    return {
      upper: { rotate: 0, transition: { duration: 0.5 } },
      fore: far
        ? {
            rotate: [0, -8, 0, -8, 0],
            transition: { duration: 1.6, repeatDelay: 0.8, repeat: Infinity },
          }
        : { rotate: 0, transition: { duration: 0.5 } },
    };
  }

  if (status === "completed") {
    return {
      upper: { rotate: [0, -3, 0], transition: { duration: 0.9 } },
      fore: { rotate: [0, -13, -4, 0], transition: { duration: 1.05 } },
    };
  }

  if (status === "failed") {
    return {
      upper: { rotate: 8, transition: { duration: 0.6 } },
      fore: { rotate: 13, transition: { duration: 0.6 } },
    };
  }

  return {
    upper: { rotate: 0, transition: { duration: 0.5 } },
    fore: { rotate: 0, transition: { duration: 0.5 } },
  };
}

function headPose(status: S, agentType: AgentType) {
  if (status === "working") {
    const movement: Record<AgentType, number[]> = {
      receptionist: [0, -4, 1, -2, 0],
      debugger: [2, 8, 1, 5, 0],
      product_manager: [-1, 5, -2, 3, 0],
      support_rep: [0, -3, 3, -1, 0],
    };

    return {
      rotate: movement[agentType],
      transition: {
        duration:
          agentType === "debugger"
            ? 2.8
            : agentType === "product_manager"
              ? 2.5
              : 2.1,
        ...loop,
      },
    };
  }

  switch (status) {
    case "queued":
      return {
        rotate: [-4, -6, -4],
        transition: { duration: 2.5, ...loop },
      };
    case "completed":
      return {
        rotate: [0, 8, -2, 0],
        transition: { duration: 0.95 },
      };
    case "failed":
      return {
        rotate: 12,
        y: 2,
        transition: { type: "spring" as const, stiffness: 90, damping: 12 },
      };
    default:
      return {
        rotate: [0, 0, -3, 0, 0, 2, 0],
        transition: { duration: 9, ...loop },
      };
  }
}

function Torso({ agentType, shirt }: { agentType: AgentType; shirt: string }) {
  if (agentType === "receptionist") {
    return (
      <g>
        <path
          d="M64 148 C59 121 63 100 73 87 L96 89 C103 108 100 133 93 148Z"
          fill={shirt}
        />
        <path d="M76 89 L84 98 L92 89" fill="#e9f5ff" opacity=".95" />
        <path d="M84 99 L84 137" stroke="#d7edff" strokeWidth="1.5" opacity=".75" />
        <circle cx="84" cy="111" r="1.6" fill="#e9f5ff" />
        <circle cx="84" cy="121" r="1.6" fill="#e9f5ff" />
      </g>
    );
  }

  if (agentType === "debugger") {
    return (
      <g>
        <path
          d="M61 148 C58 119 63 98 73 87 L99 88 C108 108 105 132 98 148Z"
          fill={shirt}
        />
        <path d="M73 89 L83 102 L93 89" fill="#d8f5ed" opacity=".9" />
        <path d="M83 102 L83 147" stroke="#176e63" strokeWidth="2" opacity=".55" />
        <path d="M91 107 L96 112 L91 117" fill="none" stroke="#d8f5ed" strokeWidth="1.6" />
      </g>
    );
  }

  if (agentType === "product_manager") {
    return (
      <g>
        <path
          d="M65 148 C60 121 65 100 75 88 L95 89 C103 109 100 134 93 148Z"
          fill={shirt}
        />
        <path d="M75 89 L84 105 L94 89" fill="#e8e0ff" opacity=".95" />
        <path d="M84 105 L84 148" stroke="#d8caff" strokeWidth="1.5" opacity=".8" />
        <circle cx="84" cy="116" r="2" fill="#e8e0ff" />
        <circle cx="84" cy="128" r="2" fill="#e8e0ff" />
      </g>
    );
  }

  return (
    <g>
      <path
        d="M61 148 C58 119 63 99 73 87 L100 88 C108 108 106 133 98 148Z"
        fill={shirt}
      />
      <path d="M73 89 L83 99 L94 89" fill="#fff0d9" opacity=".95" />
      <path d="M83 99 L83 113" stroke="#bd7934" strokeWidth="1.5" />
      <circle cx="83" cy="116" r="1.6" fill="#fff0d9" />
    </g>
  );
}

function Arm({
  status,
  far,
  look,
  agentType,
}: {
  status: S;
  far: boolean;
  look: Look;
  agentType: AgentType;
}) {
  const pose = armPose(status, far, agentType);
  const strokeWidth = agentType === "debugger" ? 12 : 11;

  return (
    <g transform={far ? "translate(5 -3)" : undefined}>
      <motion.g
        initial={false}
        animate={pose.upper}
        style={{
          originX: 0,
          originY: 0,
          ...(far ? { filter: "brightness(.84)" } : {}),
        }}
      >
        <path
          d="M84 96 L108 118"
          stroke={look.shirt}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          fill="none"
        />
        <motion.g
          initial={false}
          animate={pose.fore}
          style={{ originX: 0, originY: 0 }}
        >
          <path
            d="M108 118 L141 124"
            stroke={look.skin}
            strokeWidth="8"
            strokeLinecap="round"
            fill="none"
          />
          <circle cx="144" cy="124" r="5" fill={look.skin} />
          {agentType === "product_manager" && !far && status === "working" && (
            <path
              d="M144 121 L153 111"
              stroke="#d7a84c"
              strokeWidth="2"
              strokeLinecap="round"
            />
          )}
        </motion.g>
      </motion.g>
    </g>
  );
}

function FaceDetails({ agentType, status }: { agentType: AgentType; status: S }) {
  const failed = status === "failed";

  return (
    <g>
      {/* Ear and nose give each profile a clearer silhouette. */}
      <circle cx="72" cy="64" r="4" fill="#d99d79" opacity=".85" />
      <path
        d="M101 61 Q109 62 105 67 Q103 69 100 67"
        fill="none"
        stroke="#b77a5d"
        strokeWidth="1.6"
        strokeLinecap="round"
      />

      <path
        d={failed ? "M91 52 Q96 48 100 52" : "M91 52 Q96 50 100 52"}
        stroke="#533d35"
        strokeWidth={agentType === "debugger" ? 2 : 1.5}
        strokeLinecap="round"
        fill="none"
      />

      <motion.ellipse
        cx="95"
        cy="60"
        rx="2"
        ry="2.8"
        fill="#222a33"
        animate={{ scaleY: [1, 1, 0.1, 1, 1] }}
        transition={{
          duration: 5,
          times: [0, 0.9, 0.94, 0.98, 1],
          repeat: Infinity,
          delay: BLINK_DELAY[agentType],
        }}
      />

      {agentType === "debugger" && (
        <g fill="none" stroke="#344252" strokeWidth="1.8">
          <circle cx="95" cy="60" r="6" />
          <path d="M101 59 L105 59" />
        </g>
      )}

      {agentType === "receptionist" && (
        <g>
          <path d="M91 58 Q92 55 94 56" stroke="#fff" strokeWidth="1" opacity=".8" />
          <circle cx="72" cy="72" r="2.4" fill="#d7a64f" />
        </g>
      )}

      {agentType === "product_manager" && (
        <g fill="none" stroke="#684b39" strokeWidth="1.4" strokeLinecap="round">
          <path d="M91 54 Q95 52 99 54" />
          <path d="M92 74 Q97 77 102 73" stroke="#9b6657" />
        </g>
      )}

      {agentType === "support_rep" && (
        <g>
          <path d="M89 70 Q96 74 103 68 L101 77 Q95 82 88 77Z" fill={LOOKS.support_rep.hair} opacity=".9" />
          <path d="M92 70 Q97 72 102 69" stroke="#d39a75" strokeWidth="1" fill="none" />
        </g>
      )}

      <path
        d={failed ? "M95 73 Q99 69 103 73" : "M95 71 Q100 74 104 70"}
        stroke="#8a4f45"
        strokeWidth="1.6"
        strokeLinecap="round"
        fill="none"
      />
    </g>
  );
}

function HairBack({ agentType, look }: { agentType: AgentType; look: Look }) {
  return (
    <g>
      <path d={HAIR_BACK[look.style]} fill={look.hair} />

      {agentType === "product_manager" && (
        <g fill={look.hair}>
          <circle cx="72" cy="39" r="10" />
          <circle cx="66" cy="45" r="5" />
          <circle cx="78" cy="31" r="5" />
          <circle cx="86" cy="35" r="4" />
        </g>
      )}

      {agentType === "support_rep" && (
        <g fill={look.hair}>
          <circle cx="70" cy="48" r="5" />
          <circle cx="76" cy="39" r="5" />
          <circle cx="85" cy="35" r="5" />
          <circle cx="95" cy="37" r="5" />
          <circle cx="103" cy="45" r="5" />
          <circle cx="107" cy="54" r="4" />
        </g>
      )}
    </g>
  );
}

function HairFront({ agentType, look }: { agentType: AgentType; look: Look }) {
  return (
    <g>
      <path d={HAIR_CAP[look.style]} fill={look.hair} />

      {agentType === "receptionist" && (
        <path d="M77 54 Q84 45 96 48 Q87 50 83 59" fill={look.hair} />
      )}

      {agentType === "debugger" && (
        <path d="M72 60 L74 72 L78 72 L79 56" fill={look.hair} />
      )}

      {agentType === "product_manager" && (
        <path d="M74 49 Q78 42 85 43 Q81 49 78 56" fill={look.hair} />
      )}
    </g>
  );
}

function MonitorContent({
  agentType,
  status,
  accent,
}: {
  agentType: AgentType;
  status: S;
  accent: string;
}) {
  if (status === "completed") {
    return (
      <g>
        <circle cx="208" cy="95" r="14" fill="#173b34" />
        <path
          d="M197 95 l8 8 l15 -16"
          stroke="#4ade80"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </g>
    );
  }

  if (status === "failed") {
    return (
      <g fill="#ff7777">
        <circle cx="208" cy="96" r="14" fill="#49232b" />
        <rect x="206" y="83" width="4" height="16" rx="2" />
        <circle cx="208" cy="105" r="2.6" />
      </g>
    );
  }

  return (
    <motion.g
      animate={
        status === "working"
          ? { opacity: [0.65, 1, 0.75] }
          : { opacity: status === "queued" ? 0.55 : 0.8 }
      }
      transition={status === "working" ? { duration: 1.5, ...loop } : { duration: 0.35 }}
    >
      {agentType === "receptionist" && (
        <g>
          <rect x="190" y="81" width="27" height="29" rx="2" fill="#273747" />
          <path d="M195 88 H211 M195 94 H207 M195 100 H210" stroke={accent} strokeWidth="2.4" strokeLinecap="round" />
          <circle cx="215" cy="105" r="4" fill="#4ade80" />
        </g>
      )}

      {agentType === "debugger" && (
        <g>
          <path d="M189 103 L195 103 L199 91 L204 105 L209 96 L214 101 L222 86" stroke={accent} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          <path d="M190 109 H224" stroke="#64748b" strokeWidth="1.5" />
          <circle cx="222" cy="86" r="2.5" fill="#4ade80" />
          <path d="M190 85 H202" stroke="#dbeafe" strokeWidth="1.5" />
        </g>
      )}

      {agentType === "product_manager" && (
        <g>
          <rect x="191" y="99" width="6" height="11" rx="1" fill={accent} />
          <rect x="201" y="91" width="6" height="19" rx="1" fill={accent} opacity=".8" />
          <rect x="211" y="84" width="6" height="26" rx="1" fill={accent} opacity=".65" />
          <path d="M190 111 H225" stroke="#64748b" strokeWidth="1.5" />
          <path d="M190 86 H202" stroke="#dbeafe" strokeWidth="1.5" />
        </g>
      )}

      {agentType === "support_rep" && (
        <g>
          <path d="M190 84 Q190 80 195 80 H221 Q225 80 225 84 V101 Q225 105 221 105 H207 L199 111 V105 H195 Q190 105 190 101 Z" fill="none" stroke={accent} strokeWidth="2" strokeLinejoin="round" />
          <path d="M197 89 H217 M197 95 H213" stroke={accent} strokeWidth="2" strokeLinecap="round" />
          <circle cx="219" cy="101" r="2" fill="#4ade80" />
        </g>
      )}
    </motion.g>
  );
}

function RoleProps({
  agentType,
  status,
  accent,
}: {
  agentType: AgentType;
  status: S;
  accent: string;
}) {
  const working = status === "working";

  if (agentType === "receptionist") {
    return (
      <g>
        <rect x="252" y="119" width="31" height="8" rx="2" fill="#9aa7b5" />
        <rect x="255" y="111" width="25" height="9" rx="1" fill="#fff" />
        <path d="M260 115 H275 M260 118 H271" stroke="#aeb8c4" strokeWidth="1.5" />
        <motion.rect
          x="250"
          y="106"
          width="29"
          height="5"
          rx="1"
          fill={accent}
          animate={working ? { y: [106, 103, 106] } : { y: 106 }}
          transition={{ duration: 2, ...loop }}
        />
      </g>
    );
  }

  if (agentType === "debugger") {
    return (
      <g>
        <circle cx="269" cy="109" r="7" fill="none" stroke={accent} strokeWidth="2.5" />
        <path d="M274 114 L282 122" stroke={accent} strokeWidth="3" strokeLinecap="round" />
        <motion.circle
          cx="269"
          cy="109"
          r="2"
          fill={accent}
          animate={working ? { opacity: [0.35, 1, 0.35] } : { opacity: 0.65 }}
          transition={{ duration: 1.4, ...loop }}
        />
      </g>
    );
  }

  if (agentType === "product_manager") {
    return (
      <g>
        <rect x="241" y="72" width="15" height="15" rx="1" fill="#ffd966" transform="rotate(-6 247 78)" />
        <rect x="244" y="91" width="15" height="15" rx="1" fill="#ff9fb2" transform="rotate(5 249 96)" />
        <path d="M244 77 L252 77 M247 96 L255 96" stroke="#9b8060" strokeWidth="1.2" />
        <motion.path
          d="M263 118 H285"
          stroke={accent}
          strokeWidth="3"
          strokeLinecap="round"
          animate={working ? { opacity: [0.4, 1, 0.4] } : { opacity: 0.55 }}
          transition={{ duration: 1.8, ...loop }}
        />
      </g>
    );
  }

  return (
    <g>
      <rect x="253" y="115" width="30" height="13" rx="3" fill="#fff4e5" stroke="#e7b36f" />
      <path d="M259 120 H276 M259 124 H271" stroke="#d99a4d" strokeWidth="1.6" strokeLinecap="round" />
      <motion.circle
        cx="282"
        cy="113"
        r="3"
        fill={accent}
        animate={working ? { scale: [1, 1.4, 1] } : { scale: 1 }}
        transition={{ duration: 1.5, ...loop }}
      />
      {working && (
        <motion.path
          d="M274 98 Q281 92 287 98 M278 103 Q282 100 285 103"
          fill="none"
          stroke={accent}
          strokeWidth="1.8"
          strokeLinecap="round"
          animate={{ opacity: [0.25, 1, 0.25] }}
          transition={{ duration: 1.3, ...loop }}
        />
      )}
    </g>
  );
}

export function SeatedAgent({
  agentType,
  status,
}: {
  agentType: AgentType;
  status: S;
}) {
  const look = LOOKS[agentType];
  const failed = status === "failed";

  return (
    <svg
      viewBox="0 0 300 230"
      className="h-full w-full overflow-visible"
      role="img"
      aria-label={`${agentType.replaceAll("_", " ")} agent, ${status}`}
    >
      <ellipse cx="150" cy="213" rx="135" ry="8" fill="#1f2a3a" opacity=".1" />

      {/* Chair */}
      <rect x="44" y="92" width="9" height="58" rx="4" fill="#2c3440" />
      <rect x="44" y="146" width="56" height="9" rx="4" fill="#38424f" />
      <rect x="69" y="155" width="5" height="42" fill="#59636f" />
      <path d="M48 200 H96" stroke="#59636f" strokeWidth="5" strokeLinecap="round" />
      <circle cx="50" cy="205" r="4" fill="#2c3440" />
      <circle cx="94" cy="205" r="4" fill="#2c3440" />

      {/* Legs and queued foot tap */}
      <path d="M76 144 L128 148" stroke="#2f3a4a" strokeWidth="15" strokeLinecap="round" />
      <motion.g
        initial={false}
        animate={
          status === "queued"
            ? { rotate: [0, -9, 0, -9, 0], transition: { duration: 1.2, ...loop } }
            : { rotate: 0 }
        }
        style={{ originX: 0.25, originY: 0 }}
      >
        <path d="M128 148 L132 198" stroke="#3a4658" strokeWidth="13" strokeLinecap="round" />
        <rect x="122" y="196" width="25" height="9" rx="4" fill="#1d232c" />
      </motion.g>

      {/* Far arm is behind the body. */}
      <Arm status={status} far look={look} agentType={agentType} />

      {/* Body posture */}
      <motion.g
        initial={false}
        animate={
          failed
            ? { rotate: 4, transition: { duration: 0.7 } }
            : agentType === "debugger" && status === "working"
              ? {
                  rotate: [-1, -3, -1],
                  scaleY: [1, 1.01, 1],
                  transition: { duration: 2.8, ...loop },
                }
              : agentType === "support_rep" && status === "working"
                ? {
                    scaleY: [1, 1.018, 1],
                    rotate: [0, -1, 0],
                    transition: { duration: 2.4, ...loop },
                  }
                : {
                    scaleY: [1, 1.014, 1],
                    rotate: 0,
                    transition: { duration: status === "working" ? 2.8 : 4, ...loop },
                  }
        }
        style={{ originX: 0.5, originY: 1 }}
      >
        <Torso agentType={agentType} shirt={look.shirt} />
        <rect x="76" y="76" width="10" height="18" rx="4" fill={look.skin} />

        <motion.g
          initial={false}
          animate={headPose(status, agentType)}
          style={{ originX: 0.45, originY: 1 }}
        >
          <HairBack agentType={agentType} look={look} />
          <path d={FACE_SHAPES[agentType]} fill={look.skin} />
          <HairFront agentType={agentType} look={look} />
          <FaceDetails agentType={agentType} status={status} />

          {/* Support Rep headset */}
          {agentType === "support_rep" && (
            <g fill="none" stroke="#222a33" strokeLinecap="round">
              <path d="M76 62 C75 37 103 34 108 59" strokeWidth="3.5" />
              <path d="M79 65 V70" strokeWidth="3" />
              <rect x="75" y="59" width="7" height="13" rx="3" fill="#222a33" stroke="none" />
              <path d="M105 72 Q111 80 101 82" strokeWidth="2" />
              <circle cx="100" cy="82" r="2" fill="#222a33" stroke="none" />
            </g>
          )}
        </motion.g>

        {/* A small headset-touch gesture makes Support Rep's working state distinct. */}
        {agentType === "support_rep" && status === "working" && (
          <motion.g
            initial={false}
            animate={{ rotate: [0, -5, 0], opacity: [0.8, 1, 0.8] }}
            transition={{ duration: 2.2, ...loop }}
            style={{ originX: 0.35, originY: 0.5 }}
          >
            <path
              d="M86 96 Q99 85 101 72"
              fill="none"
              stroke={look.shirt}
              strokeWidth="8"
              strokeLinecap="round"
            />
            <circle cx="101" cy="71" r="4" fill={look.skin} />
          </motion.g>
        )}
      </motion.g>

      {/* Desk and cabinet */}
      <rect x="110" y="140" width="5" height="68" fill="#8793a1" />
      <rect x="232" y="140" width="56" height="68" fill="#c5ced8" />
      <path d="M232 163 H288 M232 186 H288" stroke="#aeb8c4" strokeWidth="2" />
      <rect x="104" y="128" width="190" height="9" rx="2" fill="#dfe5ec" />
      <rect x="104" y="137" width="190" height="3" fill="#aeb8c4" />

      {/* Role-specific workstation props */}
      <RoleProps agentType={agentType} status={status} accent={look.accent} />

      {/* Keyboard, monitor and monitor stand */}
      <rect x="134" y="123" width="30" height="5" rx="2" fill="#3a4350" />
      <rect x="180" y="70" width="56" height="50" rx="4" fill="#2b3340" />
      <rect x="185" y="75" width="46" height="40" rx="2" fill={failed ? "#3a1f26" : "#1b2430"} />
      <MonitorContent agentType={agentType} status={status} accent={look.accent} />
      <rect x="204" y="120" width="6" height="9" fill="#59636f" />
      <path d="M196 126 H218" stroke="#59636f" strokeWidth="3" strokeLinecap="round" />

      {/* Near arm is drawn over the desk. */}
      <Arm status={status} far={false} look={look} agentType={agentType} />
    </svg>
  );
}
