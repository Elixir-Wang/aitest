"use client";

import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";
import type { Agent } from "@/types/agent";

import styles from "./office-canvas.module.css";

const CHARACTER_PROFILES = [
  { hair: "#17222a", skin: "#f0bd96", shirt: "#48698b", female: false, glasses: false },
  { hair: "#553c2f", skin: "#f3c7a6", shirt: "#6f7f91", female: true, glasses: false },
  { hair: "#171d22", skin: "#e9b78e", shirt: "#4d7469", female: false, glasses: true },
  { hair: "#33251f", skin: "#f1c29e", shirt: "#7a645c", female: true, glasses: false },
  { hair: "#1d2428", skin: "#edbd99", shirt: "#567185", female: true, glasses: false },
  { hair: "#182129", skin: "#f3c8a6", shirt: "#4c6680", female: false, glasses: false },
  { hair: "#141a1e", skin: "#eab58e", shirt: "#567062", female: false, glasses: false },
  { hair: "#251c1a", skin: "#f0c09d", shirt: "#79695b", female: false, glasses: false },
  { hair: "#182027", skin: "#e8b28b", shirt: "#526f82", female: false, glasses: true },
  { hair: "#68452e", skin: "#efbf9c", shirt: "#796b85", female: true, glasses: false },
  { hair: "#151a1f", skin: "#f2c6a4", shirt: "#4f716f", female: true, glasses: false },
  { hair: "#182129", skin: "#eebc96", shirt: "#6c685f", female: false, glasses: false },
] as const;

const EXECUTIVE_PROFILE = {
  hair: "#152027",
  skin: "#f1bf98",
  shirt: "#263e61",
  female: false,
  glasses: false,
} as const;

function characterProfile(index: number) {
  return CHARACTER_PROFILES[index % CHARACTER_PROFILES.length];
}

export function SiliconOfficeCanvas({
  agents,
  onAgentSelect,
}: {
  agents: Agent[];
  onAgentSelect: (agentId: string) => void;
}) {
  const workingCount = agents.filter((agent) => agent.state === "working" || agent.state === "thinking").length;

  return (
    <section
      aria-label="硅基员工动态办公室"
      className={cn(
        styles.scene,
        "relative h-full min-h-[1680px] w-full overflow-hidden sm:min-h-[1460px] xl:min-h-[1280px]",
      )}
    >
      <div className={cn(styles.floorWash, "pointer-events-none absolute inset-0")} />

      <ExecutiveStation workingCount={workingCount} />

      <div className="absolute top-[390px] right-5 bottom-8 left-5 grid grid-cols-2 content-stretch gap-x-4 gap-y-5 sm:top-[400px] sm:grid-cols-3 sm:gap-x-6 sm:gap-y-4 xl:top-[420px] xl:right-10 xl:left-10 xl:grid-cols-4 xl:gap-x-8 xl:gap-y-4">
        {agents.map((agent, index) => (
          <AgentDesk agent={agent} index={index} key={agent.id} onSelect={onAgentSelect} />
        ))}
      </div>
    </section>
  );
}

function ExecutiveStation({ workingCount }: { workingCount: number }) {
  return (
    <div className="absolute top-[145px] left-1/2 z-10 h-[230px] w-[330px] -translate-x-1/2 sm:top-[155px] xl:top-[175px] xl:w-[360px]">
      <span className="absolute -top-3 left-1/2 z-40 flex -translate-x-1/2 items-center gap-2 whitespace-nowrap rounded-full bg-[#2f6fe4] px-4 py-1.5 font-medium text-white text-xs shadow-[0_7px_20px_rgba(33,83,170,0.24)]">
        <span className="size-1.5 rounded-full bg-white" />
        AI 测试总控
      </span>
      <div className="absolute top-[10px] left-1/2 z-10 h-[142px] w-[122px] -translate-x-1/2">
        <LayeredChibi executive index={0} />
      </div>
      <div className="absolute right-0 bottom-6 left-0 z-20 h-[122px]">
        <DeskIllustration active executive index={99} skin={EXECUTIVE_PROFILE.skin} />
      </div>
      <div className="absolute right-[18%] bottom-7 left-[18%] z-30 text-center">
        <strong className="block truncate font-semibold text-[#44382f] text-sm">智能体调度中心</strong>
        <span className="mt-0.5 block text-[#68737d] text-[10px]">{workingCount} 个任务运行中</span>
      </div>
    </div>
  );
}

function AgentDesk({ agent, index, onSelect }: { agent: Agent; index: number; onSelect: (agentId: string) => void }) {
  const status = resolveStatus(agent);

  return (
    <button
      aria-label={`${agent.name}，${status.label}`}
      className="group relative min-h-0 w-full max-w-[260px] justify-self-center rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3478ef] focus-visible:ring-offset-2 active:translate-y-px"
      onClick={() => onSelect(agent.id)}
      type="button"
    >
      <span className="absolute top-0 left-1/2 z-40 flex -translate-x-1/2 items-center gap-1.5 whitespace-nowrap rounded-full border border-white/80 bg-white/94 px-3 py-1.5 font-medium text-[10px] shadow-[0_5px_16px_rgba(42,55,68,0.12)] backdrop-blur-sm">
        <span
          className={cn(styles.statusDot, "size-2 rounded-full")}
          style={{ "--status-color": status.color, backgroundColor: status.color } as CSSProperties}
        />
        <span style={{ color: status.color }}>{status.label}</span>
      </span>

      <span className="absolute top-[4px] left-1/2 z-10 h-[122px] w-[106px] -translate-x-1/2 transition-transform duration-300 group-hover:-translate-y-1 group-hover:scale-[1.02] sm:top-[24px] sm:h-[150px] sm:w-[130px] xl:top-[26px] xl:h-[160px] xl:w-[138px]">
        <LayeredChibi index={index} />
      </span>

      <span className="absolute right-0 bottom-[27px] left-0 z-20 h-[96px] transition-transform duration-300 group-hover:-translate-y-0.5 sm:bottom-[31px] sm:h-[112px]">
        <DeskIllustration active={status.active} index={index} skin={characterProfile(index).skin} />
      </span>

      <span className="absolute right-[14%] bottom-[51px] left-[14%] z-30 truncate text-center font-semibold text-[#4d4037] text-[11px] sm:bottom-[56px] sm:text-xs">
        {agent.name}
      </span>
      <span className="absolute right-[10%] bottom-0 left-[10%] z-30 block truncate rounded-[3px] bg-white/84 px-2 py-1 text-[#697580] text-[9px] shadow-[0_3px_10px_rgba(48,58,69,0.08)] backdrop-blur-sm">
        {agent.currentTask ?? "等待任务"}
      </span>
    </button>
  );
}

function LayeredChibi({ index, executive = false }: { index: number; executive?: boolean }) {
  const profile = executive ? EXECUTIVE_PROFILE : characterProfile(index);
  const hairStyle = index % 4;
  const animationDelay = `${-((index * 1.43) % 8).toFixed(2)}s`;

  return (
    <svg aria-hidden="true" className="h-full w-full overflow-visible" viewBox="0 0 120 150">
      <ellipse cx="60" cy="145" fill="#31404b" opacity="0.13" rx="35" ry="4" />
      <g className={styles.bodyBreath} style={{ animationDelay }}>
        <path d="M28 146c1-25 13-37 32-37s31 12 32 37H28Z" fill={profile.shirt} />
        <path d="m44 112 16 18 16-18-8-5H52l-8 5Z" fill="#f7f8f8" />
        {executive ? <path d="m58 124 2 13 2-13-2-4-2 4Z" fill="#315d9d" /> : null}
        <ellipse cx="31" cy="137" fill={profile.skin} rx="8" ry="12" />
        <ellipse cx="89" cy="137" fill={profile.skin} rx="8" ry="12" />
      </g>

      <g className={styles.headMotion} style={{ animationDelay }}>
        {profile.female ? (
          <path d="M26 49c0-28 16-39 34-39 22 0 36 15 35 43l-5 55-17 10H45l-17-11-2-58Z" fill={profile.hair} />
        ) : (
          <path d="M27 53c-1-27 12-42 34-42 23 0 35 16 33 43l-8 31H34l-7-32Z" fill={profile.hair} />
        )}

        <ellipse cx="27" cy="68" fill={profile.skin} rx="8" ry="11" />
        <ellipse cx="93" cy="68" fill={profile.skin} rx="8" ry="11" />
        <path d="M31 52c0-24 11-35 29-35 19 0 30 12 30 35v27c0 20-13 33-30 33S31 99 31 79V52Z" fill={profile.skin} />

        {hairStyle === 0 ? (
          <path d="M29 52c1-26 13-39 33-39 18 0 29 11 30 32-14-1-23-6-30-14-8 9-18 15-33 17v4Z" fill={profile.hair} />
        ) : null}
        {hairStyle === 1 ? (
          <path d="M29 55c-1-28 12-42 33-42 17 0 28 10 31 30-11 1-21-4-28-13-9 11-20 18-36 20v5Z" fill={profile.hair} />
        ) : null}
        {hairStyle === 2 ? (
          <path d="M29 50c3-27 16-39 36-36 14 2 23 12 27 29-18 0-31-5-39-15-5 9-13 15-24 18v4Z" fill={profile.hair} />
        ) : null}
        {hairStyle === 3 ? (
          <path d="M29 55c0-27 12-41 31-41 20 0 31 13 32 37-10-3-20-10-25-20-9 10-21 17-38 20v4Z" fill={profile.hair} />
        ) : null}

        <path
          d="M41 57c5-3 10-3 15 0"
          fill="none"
          opacity="0.6"
          stroke="#493329"
          strokeLinecap="round"
          strokeWidth="2"
        />
        <path
          d="M65 57c5-3 10-3 15 0"
          fill="none"
          opacity="0.6"
          stroke="#493329"
          strokeLinecap="round"
          strokeWidth="2"
        />

        <g className={styles.blinkEyes} style={{ animationDelay }}>
          <ellipse cx="49" cy="68" fill="#24282a" rx="5.3" ry="7" />
          <ellipse cx="72" cy="68" fill="#24282a" rx="5.3" ry="7" />
          <circle cx="47.5" cy="66" fill="white" r="1.7" />
          <circle cx="70.5" cy="66" fill="white" r="1.7" />
        </g>

        {profile.glasses ? (
          <g fill="none" stroke="#35434d" strokeWidth="2.2">
            <rect height="17" rx="7" width="21" x="37" y="61" />
            <rect height="17" rx="7" width="21" x="63" y="61" />
            <path d="M58 68h5M31 66l6 2M84 68l6-2" />
          </g>
        ) : null}

        <ellipse cx="42" cy="82" fill="#e89b92" opacity="0.42" rx="6" ry="2.6" />
        <ellipse cx="79" cy="82" fill="#e89b92" opacity="0.42" rx="6" ry="2.6" />
        <path d="M56 88c3 3 6 3 9 0" fill="none" stroke="#a45f59" strokeLinecap="round" strokeWidth="1.7" />
      </g>
    </svg>
  );
}

function DeskIllustration({
  active,
  index,
  skin,
  executive = false,
}: {
  active: boolean;
  index: number;
  skin: string;
  executive?: boolean;
}) {
  const gradientId = `desk-surface-${index}`;
  const glowId = `desk-glow-${index}`;

  return (
    <svg aria-hidden="true" className="h-full w-full overflow-visible" viewBox="0 0 280 110">
      <defs>
        <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor={executive ? "#d5b18a" : "#ffffff"} />
          <stop offset="1" stopColor={executive ? "#b88963" : "#edf0f2"} />
        </linearGradient>
        <filter height="200%" id={glowId} width="160%" x="-30%" y="-50%">
          <feGaussianBlur stdDeviation="4" />
        </filter>
      </defs>

      <ellipse cx="140" cy="103" fill="#344453" opacity="0.18" rx="122" ry="6" />
      {active ? (
        <ellipse
          className={styles.screenGlow}
          cx="140"
          cy="101"
          fill="#5c91ee"
          filter={`url(#${glowId})`}
          opacity="0.5"
          rx="104"
          ry="5"
        />
      ) : null}

      <path d="M20 58h240l-9 12H29L20 58Z" fill={`url(#${gradientId})`} stroke="#c6ccd2" />
      <path d="M29 70h222v27H29V70Z" fill={executive ? "#f2eee9" : "#f8f9fa"} stroke="#c8cdd2" />
      <path d="M34 96v9M246 96v9" stroke="#77828c" strokeLinecap="round" strokeWidth="4" />

      <g>
        <rect fill="#2d3740" height="35" rx="3" width="68" x="106" y="20" />
        <rect fill="#101820" height="28" rx="1" width="60" x="110" y="24" />
        <rect
          className={active ? styles.screenGlow : undefined}
          fill={active ? "#316fb8" : "#53606a"}
          height="24"
          opacity={active ? 0.58 : 0.2}
          width="56"
          x="112"
          y="26"
        />
        <path d="M137 55h6v8h-6zM126 64h28" fill="none" stroke="#77818a" strokeLinecap="round" strokeWidth="3" />
      </g>

      <g>
        <ellipse cx="93" cy="57" fill={skin} rx="9" ry="4.5" />
        <ellipse cx="187" cy="57" fill={skin} rx="9" ry="4.5" />
        <path d="M86 58h14M180 58h14" opacity="0.18" stroke="#8f5f4d" strokeLinecap="round" />
      </g>

      <g transform="translate(36 36)">
        <path d="M7 20h15l-2 17H9L7 20Z" fill="#8fa49a" />
        <path d="M14 21C4 14 4 5 7 3c6 3 8 9 7 18ZM15 21c9-7 11-15 8-18-6 2-9 9-8 18Z" fill="#5d8b6d" />
        <path d="M14 20C9 10 13 3 16 1c4 5 3 12-2 19Z" fill="#72a17b" />
      </g>

      <g transform="translate(225 32)">
        <rect fill="#75879a" height="25" rx="2" width="5" x="0" y="9" />
        <rect fill="#c48a58" height="29" rx="2" width="5" x="6" y="5" />
        <rect fill="#e0b85d" height="22" rx="2" width="5" x="12" y="12" />
        <path d="M-3 34h23" stroke="#84919c" strokeLinecap="round" strokeWidth="2" />
      </g>

      {executive ? (
        <g transform="translate(65 37)">
          <ellipse cx="9" cy="21" fill="#6b4d38" rx="10" ry="4" />
          <path d="M1 7h16l-2 15H3L1 7Z" fill="#f3f1ed" stroke="#b6a491" />
          <path d="M17 10c8 0 8 9 0 9" fill="none" stroke="#b6a491" strokeWidth="2" />
        </g>
      ) : null}
    </svg>
  );
}

function resolveStatus(agent: Agent) {
  if (agent.state === "working") return { label: "工作中", color: "#27aa79", active: true };
  if (agent.state === "thinking") return { label: "专注中", color: "#3478ef", active: true };
  if (agent.state === "talking") return { label: "协作中", color: "#ec8b2d", active: true };
  return { label: "空闲", color: "#98a2ad", active: false };
}
