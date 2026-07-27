"use client";

import { type CSSProperties, useEffect, useRef, useState } from "react";

import { SCENE_HEIGHT, SCENE_WIDTH } from "@/scene/layout/officeLayout";
import { OfficeScene } from "@/scene/OfficeScene";
import type { Agent } from "@/types/agent";

import styles from "./office-canvas.module.css";

export function SiliconOfficeCanvas({
  agents,
  onAgentSelect,
}: {
  agents: Agent[];
  onAgentSelect: (agentId: string) => void;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<OfficeScene | null>(null);
  const selectRef = useRef(onAgentSelect);
  const agentsRef = useRef(agents);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    selectRef.current = onAgentSelect;
  }, [onAgentSelect]);

  useEffect(() => {
    agentsRef.current = agents;
  }, [agents]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    let disposed = false;
    const scene = new OfficeScene({
      agents: agentsRef.current,
      onAgentClick: ({ agent }) => selectRef.current(agent.id),
    });
    const resize = () => {
      const bounds = host.getBoundingClientRect();
      scene.resize(Math.max(1, bounds.width), Math.max(1, bounds.height));
    };
    const observer = new ResizeObserver(resize);
    observer.observe(host);

    void scene.init(host, Math.max(1, host.clientWidth), Math.max(1, host.clientHeight)).then(() => {
      if (disposed) return;
      sceneRef.current = scene;
      scene.updateAgents(agentsRef.current);
      resize();
      setReady(true);
    });

    return () => {
      disposed = true;
      observer.disconnect();
      if (sceneRef.current === scene) sceneRef.current = null;
      scene.destroy();
    };
  }, []);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    scene.updateAgents(agents);
  }, [agents]);

  return (
    <section aria-label="硅基员工动态办公室" className={styles.scene}>
      <div className={styles.sceneFrame}>
        <div aria-hidden="true" className={styles.canvasHost} ref={hostRef} />

        <fieldset className={styles.hitLayer}>
          <legend className={styles.srOnly}>员工工位</legend>
          {agents.map((agent) => (
            <button
              aria-label={`${agent.name}，${statusLabel(agent)}，${agent.currentTask ?? "等待任务"}`}
              className={styles.agentHitTarget}
              data-department={agent.department}
              key={agent.id}
              onClick={() => onAgentSelect(agent.id)}
              style={
                {
                  "--agent-color": `#${agent.color.toString(16).padStart(6, "0")}`,
                  left: `${(agent.x / SCENE_WIDTH) * 100}%`,
                  top: `${(agent.y / SCENE_HEIGHT) * 100}%`,
                } as CSSProperties
              }
              type="button"
            />
          ))}
        </fieldset>

        {!ready ? <div className={styles.loading}>正在布置硅基员工办公室…</div> : null}
      </div>
    </section>
  );
}

function statusLabel(agent: Agent) {
  if (agent.state === "working") return "工作中";
  if (agent.state === "thinking") return "专注中";
  if (agent.state === "talking") return "协作中";
  if (agent.state === "walking") return "移动中";
  return "空闲";
}
