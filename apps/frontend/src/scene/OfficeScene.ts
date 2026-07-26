import type { FederatedPointerEvent } from "pixi.js";
import { Application, Container, Graphics, Sprite } from "pixi.js";

import { getOfficeBackgroundTexture, loadOfficeAssets } from "@/scene/assets/loadOfficeAssets";
import { loadSpineAssets } from "@/scene/assets/loadSpineAssets";
import { AgentEntity } from "@/scene/entities/AgentEntity";
import { DeskEntity } from "@/scene/entities/DeskEntity";
import { buildOfficeDesks, COLORS, SCENE_HEIGHT, SCENE_WIDTH } from "@/scene/layout/officeLayout";
import { AnimationSystem } from "@/scene/systems/AnimationSystem";
import { MovementSystem, type WalkPoint } from "@/scene/systems/MovementSystem";
import type { Agent, Desk, DeskVisitMission } from "@/types/agent";

const FRONT_AISLE_Y = SCENE_HEIGHT - 68;
const WALK_EPSILON = 3;
const HANDOFF_OFFSET_X = 66;

type MovementGoal = {
  kind: "handoff" | "handoff-return";
  resume: Pick<Agent, "state" | "currentTask" | "assignedDeskId">;
  destination: WalkPoint;
  home: WalkPoint;
  mission?: DeskVisitMission;
};

type HandoffPause = {
  until: number;
  home: WalkPoint;
  resume: MovementGoal["resume"];
};

export type OfficeAgentClick = {
  agent: Agent;
  rosterNo: number;
  clientX: number;
  clientY: number;
};

export class OfficeScene {
  private app: Application | null = null;
  private world: Container | null = null;
  private destroyed = false;
  private agentEntities = new Map<string, AgentEntity>();
  private deskEntities = new Map<string, DeskEntity>();
  private officeLayer: Container | null = null;

  private animation = new AnimationSystem();
  private movement = new MovementSystem();
  private movementGoals = new Map<string, MovementGoal>();
  private handoffPauses = new Map<string, HandoffPause>();
  private handledMissions = new Map<string, string>();
  private elapsed = 0;

  private agents: Agent[];
  private desks: Desk[];
  private readonly options: {
    onAgentClick?: (event: OfficeAgentClick) => void;
  };

  constructor(options: { agents?: Agent[]; desks?: Desk[]; onAgentClick?: (event: OfficeAgentClick) => void } = {}) {
    this.options = { onAgentClick: options.onAgentClick };
    this.agents = (options.agents ?? []).map((agent) => ({ ...agent }));
    this.desks = (options.desks ?? buildOfficeDesks(this.agents.length)).map((desk) => ({ ...desk }));
  }

  async init(container: HTMLElement, width: number, height: number) {
    const app = new Application();
    await app.init({
      width,
      height,
      backgroundColor: COLORS.floor,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
    });

    this.app = app;
    container.appendChild(app.canvas);

    this.world = new Container();
    app.stage.addChild(this.world);
    this.fitStage(width, height);

    await loadSpineAssets();
    const officeOk = await loadOfficeAssets();
    if (this.destroyed) {
      app.destroy(true, { children: true });
      return;
    }
    if (!officeOk) {
      console.error(
        "[Office] desk.png / chair.png 加载失败，工位将使用矢量占位图。请检查 public/assets/office/ 并硬刷新。",
      );
    }

    this.drawMap(this.world);
    this.spawnOffice(this.world);
    this.pushDataToEntities();

    app.ticker.add(this.onTick);
  }

  updateAgents(nextAgents: Agent[]) {
    const previousCount = this.agents.length;
    this.agents = nextAgents.map((agent) => ({ ...agent }));
    if (!this.officeLayer) return;

    if (previousCount !== this.agents.length) {
      this.rebuildDesks(buildOfficeDesks(this.agents.length));
    }
    this.reconcileAgents();
  }

  resize(containerWidth: number, containerHeight: number) {
    if (!this.app || !this.world) return;
    this.app.renderer.resize(containerWidth, containerHeight);
    this.fitStage(containerWidth, containerHeight);
  }

  /** 等比缩放完整办公室场景并居中，任何屏幕比例下都不裁切内容 */
  private fitStage(containerWidth: number, containerHeight: number) {
    if (!this.world) return;

    const scale = Math.min(containerWidth / SCENE_WIDTH, containerHeight / SCENE_HEIGHT);
    const offsetX = (containerWidth - SCENE_WIDTH * scale) / 2;
    const offsetY = (containerHeight - SCENE_HEIGHT * scale) / 2;

    this.world.scale.set(scale);
    this.world.position.set(offsetX, offsetY);

    const canvas = this.app?.canvas as HTMLCanvasElement | undefined;
    if (!canvas) return;
    canvas.style.display = "block";
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    canvas.style.maxWidth = "100%";
    canvas.style.maxHeight = "100%";
  }

  destroy() {
    this.destroyed = true;
    this.app?.ticker.remove(this.onTick);
    this.app?.destroy(true, { children: true });
    this.app = null;
    this.world = null;
    this.agentEntities.clear();
    this.deskEntities.clear();
    this.movementGoals.clear();
    this.handoffPauses.clear();
    this.handledMissions.clear();
    this.officeLayer = null;
  }

  private onTick = (ticker: { deltaTime: number }) => {
    const dt = Math.min(ticker.deltaTime / 60, 0.05);

    this.elapsed += dt;
    for (const entity of this.movement.update(this.agentEntities, dt)) {
      this.finishMovement(entity);
    }
    this.resumePausedHandoffs();

    this.animation.update(this.agentEntities, dt);
    this.sortOfficeDepth();
    this.syncDeskOccupancy();
  };

  private sortOfficeDepth() {
    if (!this.officeLayer) return;

    const agentPositions = [...this.agentEntities.values()].map((e) => ({
      x: e.position.x,
      y: e.position.y,
    }));

    for (const e of this.agentEntities.values()) {
      e.zIndex = e.position.y;
    }

    for (const desk of this.deskEntities.values()) {
      desk.updateDepthZ(agentPositions);
    }

    this.officeLayer.sortChildren();
  }

  private pushDataToEntities() {
    for (const agent of this.agents) {
      const entity = this.agentEntities.get(agent.id);
      if (!entity) continue;

      const prev = entity.data;
      entity.apply(agent);
      if (prev.x !== agent.x || prev.y !== agent.y || agent.state !== "walking") {
        entity.setPosition(agent.x, agent.y);
      }
    }
  }

  private reconcileAgents() {
    if (!this.officeLayer) return;

    const incomingIds = new Set(this.agents.map((agent) => agent.id));
    for (const [agentId, entity] of this.agentEntities) {
      if (incomingIds.has(agentId)) continue;
      this.movementGoals.delete(agentId);
      this.handoffPauses.delete(agentId);
      this.handledMissions.delete(agentId);
      entity.removeFromParent();
      entity.destroy({ children: true });
      this.agentEntities.delete(agentId);
    }

    for (const agent of this.agents) {
      const existing = this.agentEntities.get(agent.id);
      if (!existing) {
        this.spawnAgent(agent);
        continue;
      }

      this.syncExistingAgent(existing, agent);
    }
  }

  private syncExistingAgent(entity: AgentEntity, incoming: Agent) {
    entity.apply({
      name: incoming.name,
      color: incoming.color,
      visualScale: incoming.visualScale,
      currentTask: incoming.currentTask,
      assignedDeskId: incoming.assignedDeskId,
      bubbleText: incoming.bubbleText,
      customAnimation: incoming.customAnimation,
    });

    const missionKey = incoming.mission ? this.missionKey(incoming.mission) : "";
    const activeHandoff = this.movementGoals.has(incoming.id) || this.handoffPauses.has(incoming.id);
    if (incoming.mission && missionKey !== this.handledMissions.get(incoming.id) && !activeHandoff) {
      this.startHandoff(entity, incoming, incoming.mission, missionKey);
      return;
    }

    if (!incoming.mission && !activeHandoff) this.handledMissions.delete(incoming.id);
    if (activeHandoff) {
      const goal = this.movementGoals.get(incoming.id);
      if (goal) goal.resume = this.resumeState(incoming);
      const pause = this.handoffPauses.get(incoming.id);
      if (pause) pause.resume = this.resumeState(incoming);
      return;
    }

    this.movement.cancel(entity);
    entity.hideBubble();
    entity.apply({
      state: incoming.state,
      facing: incoming.facing,
      viewFacing: incoming.viewFacing,
      mission: incoming.mission,
    });
    entity.setPosition(incoming.x, incoming.y);
  }

  private startHandoff(entity: AgentEntity, incoming: Agent, mission: DeskVisitMission, missionKey: string) {
    const host = this.agentEntities.get(mission.hostAgentId);
    if (!host || host.agentId === entity.agentId) return;

    const side = entity.position.x <= host.position.x ? -1 : 1;
    const destination = {
      x: host.position.x + side * HANDOFF_OFFSET_X,
      y: host.position.y + 16,
    };
    const home = { x: incoming.x, y: incoming.y };
    this.handledMissions.set(incoming.id, missionKey);
    this.movementGoals.set(incoming.id, {
      kind: "handoff",
      resume: this.resumeState(incoming),
      destination,
      home,
      mission,
    });
    if (!this.movement.start(entity, this.officePath(entity.position, destination))) {
      this.finishMovement(entity);
    }
  }

  private resumePausedHandoffs() {
    for (const [agentId, pause] of this.handoffPauses) {
      if (pause.until > this.elapsed) continue;
      this.handoffPauses.delete(agentId);
      const entity = this.agentEntities.get(agentId);
      if (!entity) continue;

      entity.hideBubble();
      this.movementGoals.set(agentId, {
        kind: "handoff-return",
        resume: pause.resume,
        destination: pause.home,
        home: pause.home,
      });
      if (!this.movement.start(entity, this.officePath(entity.position, pause.home))) {
        this.finishMovement(entity);
      }
    }
  }

  private finishMovement(entity: AgentEntity) {
    const goal = this.movementGoals.get(entity.agentId);
    this.movementGoals.delete(entity.agentId);
    if (!goal) {
      entity.apply({ state: "idle" });
      return;
    }

    if (goal.kind === "handoff" && goal.mission) {
      entity.apply({
        state: "talking",
        currentTask: `向 ${this.agentEntities.get(goal.mission.hostAgentId)?.data.name ?? "协作智能体"}交接`,
        mission: { ...goal.mission, phase: "talk" },
      });
      entity.showBubble(goal.mission.message, goal.mission.talkDuration);
      this.handoffPauses.set(entity.agentId, {
        until: this.elapsed + goal.mission.talkDuration,
        home: goal.home,
        resume: goal.resume,
      });
      return;
    }

    entity.hideBubble();
    entity.apply({
      state: goal.resume.state,
      currentTask: goal.resume.currentTask,
      assignedDeskId: goal.resume.assignedDeskId,
      facing: 1,
      viewFacing: "front",
      mission: undefined,
    });
  }

  private officePath(from: WalkPoint, to: WalkPoint): WalkPoint[] {
    if (Math.abs(from.x - to.x) <= WALK_EPSILON || Math.abs(from.y - to.y) <= WALK_EPSILON) return [to];
    return [{ x: from.x, y: FRONT_AISLE_Y }, { x: to.x, y: FRONT_AISLE_Y }, to];
  }

  private resumeState(agent: Agent): MovementGoal["resume"] {
    return {
      state: agent.state === "walking" ? "idle" : agent.state,
      currentTask: agent.currentTask,
      assignedDeskId: agent.assignedDeskId,
    };
  }

  private missionKey(mission: DeskVisitMission) {
    return [mission.hostAgentId, mission.hostDeskId, mission.message, mission.resumeTask].join(":");
  }

  private syncDeskOccupancy() {
    const occupied = new Set(
      this.agents.flatMap((agent) => (agent.state === "working" && agent.assignedDeskId ? [agent.assignedDeskId] : [])),
    );
    for (const desk of this.deskEntities.values()) {
      desk.setOccupied(occupied.has(desk.deskId));
    }
  }

  /** 桌子 / 人物 / 椅子同层；桌沿为界动态遮挡 */
  private spawnOffice(parent: Container) {
    const layer = new Container();
    layer.label = "office";
    layer.sortableChildren = true;
    this.officeLayer = layer;

    for (const desk of this.desks) {
      const entity = new DeskEntity(desk);
      this.deskEntities.set(desk.id, entity);
      layer.addChild(entity.shadowGfx, entity.deskLayer, entity.chairLayer, entity.occupiedIndicator);
    }

    for (const agent of this.agents) {
      this.spawnAgent(agent);
    }

    this.sortOfficeDepth();
    parent.addChild(layer);
  }

  private spawnAgent(agent: Agent) {
    if (!this.officeLayer) throw new Error("Office layer is not ready");
    const entity = new AgentEntity(agent);
    this.agentEntities.set(agent.id, entity);
    entity.zIndex = agent.y;
    entity.on("pointertap", (event: FederatedPointerEvent) => {
      event.stopPropagation();
      this.options.onAgentClick?.({
        agent: { ...entity.data },
        rosterNo: this.agents.findIndex((candidate) => candidate.id === entity.agentId) + 1,
        clientX: event.clientX,
        clientY: event.clientY,
      });
    });
    this.officeLayer.addChild(entity);
    return entity;
  }

  private rebuildDesks(nextDesks: Desk[]) {
    if (!this.officeLayer) return;
    for (const entity of this.deskEntities.values()) entity.destroy();
    this.deskEntities.clear();
    this.desks = nextDesks.map((desk) => ({ ...desk }));
    for (const desk of this.desks) {
      const entity = new DeskEntity(desk);
      this.deskEntities.set(desk.id, entity);
      this.officeLayer.addChild(entity.shadowGfx, entity.deskLayer, entity.chairLayer, entity.occupiedIndicator);
    }
  }

  private drawMap(parent: Container) {
    const map = new Container();
    map.label = "map";

    const floor = new Graphics();
    floor.rect(0, 0, SCENE_WIDTH, SCENE_HEIGHT);
    floor.fill(COLORS.floor);
    map.addChild(floor);

    const bgTex = getOfficeBackgroundTexture();
    if (bgTex) {
      const bg = new Sprite(bgTex);
      const scale = Math.min(SCENE_WIDTH / bgTex.width, SCENE_HEIGHT / bgTex.height);
      bg.scale.set(scale);
      bg.position.set((SCENE_WIDTH - bgTex.width * scale) / 2, (SCENE_HEIGHT - bgTex.height * scale) / 2);
      map.addChild(bg);
    }

    parent.addChildAt(map, 0);
  }
}
