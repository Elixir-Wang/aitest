import { Container, Graphics, Rectangle } from "pixi.js";

import { isSpineReady } from "@/scene/assets/loadSpineAssets";
import { getCharacterProfile } from "@/scene/characters/character-manifest";
import { SpineCharacter } from "@/scene/characters/SpineCharacter";
import { resolveWalkViewFacing, viewFacingToLR } from "@/scene/systems/movementFacing";
import { Bubble } from "@/scene/ui/Bubble";
import { StatusLabel } from "@/scene/ui/StatusLabel";
import type { Agent, AgentState } from "@/types/agent";

export class AgentEntity extends Container {
  readonly agentId: string;
  readonly overlayLayer = new Container();
  private agent: Agent;
  private spineChar: SpineCharacter | null = null;
  private fallbackBody: Graphics | null = null;
  private fallbackScarf: Graphics | null = null;
  private statusLabel: StatusLabel;
  private bubble: Bubble;
  private walkPhase = 0;
  private useSpine = false;
  private readonly profile;
  private readonly roleAccessories = new Graphics();
  private readonly behaviorSeed: number;
  private idleElapsed = 0;
  private nextBehaviorAt: number;
  private reducedMotion = false;

  constructor(agent: Agent) {
    super();
    this.agentId = agent.id;
    this.agent = { ...agent };
    this.profile = getCharacterProfile(agent.characterProfileId ?? agent.id);
    this.behaviorSeed = stableBehaviorSeed(agent.id);
    this.nextBehaviorAt = 8 + (this.behaviorSeed % 7);

    this.statusLabel = new StatusLabel(agent.name);
    this.bubble = new Bubble();

    if (isSpineReady()) {
      this.spineChar = new SpineCharacter(agent.id, agent.color);
      if (this.spineChar.isReady) {
        this.useSpine = true;
        this.spineChar.setAgentColor(agent.color);
        this.spineChar.setFacing(agent.facing);
        this.spineChar.setViewFacing(agent.viewFacing ?? "front");
        this.spineChar.playState(agent.state);
        this.addChild(this.spineChar);
      } else {
        this.spineChar.destroy();
        this.spineChar = null;
        this.initFallbackGraphics();
      }
    } else {
      this.initFallbackGraphics();
    }

    this.overlayLayer.eventMode = "none";
    this.overlayLayer.addChild(this.statusLabel, this.bubble);

    this.mountRoleAccessories();
    this.addChild(this.roleAccessories);

    this.eventMode = "static";
    this.cursor = "pointer";
    this.hitArea = new Rectangle(-84, -92, 168, 210);

    this.syncVisual();
    this.setPosition(agent.x, agent.y);
    this.setVisualScale(agent.visualScale ?? 1);
  }

  get data(): Agent {
    return this.agent;
  }

  apply(patch: Partial<Agent>) {
    const prevState = this.agent.state;
    const prevFacing = this.agent.facing;
    const prevViewFacing = this.agent.viewFacing;
    const prevColor = this.agent.color;
    const prevCustomAnimation = this.agent.customAnimation;
    const prevBubbleText = this.agent.bubbleText;
    const prevVisualScale = this.agent.visualScale;
    this.agent = { ...this.agent, ...patch };
    if (patch.state != null && patch.state !== "idle") this.wakeFromRest();

    this.statusLabel.setName(this.agent.name);
    this.statusLabel.setState(this.agent.state);
    this.statusLabel.setTask(this.agent.currentTask);
    if (patch.bubbleText !== undefined && patch.bubbleText !== prevBubbleText) {
      this.bubble.show(patch.bubbleText);
    }
    if (patch.visualScale != null && patch.visualScale !== prevVisualScale) {
      this.setVisualScale(patch.visualScale);
    }

    if (this.useSpine && this.spineChar) {
      if (patch.viewFacing != null && patch.viewFacing !== prevViewFacing) {
        this.spineChar.setViewFacing(patch.viewFacing);
      }
      if (patch.facing != null && patch.facing !== prevFacing) {
        this.spineChar.setFacing(patch.facing);
      }
      if ((patch.state != null && patch.state !== prevState) || patch.customAnimation !== prevCustomAnimation) {
        this.spineChar.playState(this.agent.state, this.agent.customAnimation);
      }
      if (patch.color != null && patch.color !== prevColor) {
        this.spineChar.setAgentColor(patch.color);
      }
      this.updateOverlayPositions();
    } else {
      this.syncVisual();
    }
  }

  setPosition(x: number, y: number) {
    this.agent.x = x;
    this.agent.y = y;
    this.position.set(x, y);
    this.overlayLayer.position.set(x, y);
  }

  setVisualScale(scale: number) {
    this.scale.set(scale);
    this.overlayLayer.scale.set(scale);
  }

  showBubble(text: string, duration = 4) {
    this.agent.bubbleText = text;
    this.bubble.show(text, duration);
    this.updateOverlayPositions();
  }

  hideBubble() {
    this.agent.bubbleText = undefined;
    this.bubble.hide();
  }

  playCustomAnimation(animation: string, task?: string) {
    this.wakeFromRest();
    this.agent = {
      ...this.agent,
      state: "talking",
      currentTask: task,
      customAnimation: animation,
      viewFacing: "front",
      facing: 1,
      targetX: undefined,
      targetY: undefined,
      walkPath: undefined,
      walkPathIndex: undefined,
      mission: undefined,
      bubbleText: undefined,
    };

    if (this.useSpine && this.spineChar) {
      this.spineChar.setViewFacing("front");
      this.spineChar.setFacing(1);
      this.spineChar.playAnimation(animation);
      this.updateOverlayPositions();
      return;
    }

    this.syncVisual();
  }

  updateVisuals(state: AgentState, dt: number) {
    this.updatePresentation(state, dt);
    if (this.useSpine && this.spineChar) {
      if (state === "walking" && this.agent.targetX != null && this.agent.targetY != null) {
        const viewFacing = resolveWalkViewFacing(this.agent.targetX - this.agent.x, this.agent.targetY - this.agent.y);
        this.agent.viewFacing = viewFacing;
        this.agent.facing = viewFacingToLR(viewFacing);
        this.spineChar.setViewFacing(viewFacing);
        this.spineChar.setFacing(this.agent.facing);
      } else if (this.agent.viewFacing !== "front") {
        this.agent.viewFacing = "front";
        this.spineChar.setViewFacing("front");
      }
      this.spineChar.playState(state, this.agent.customAnimation);
    } else {
      this.walkPhase += dt * 8;
      this.drawFallbackBody(state, 0);
    }

    this.bubble.update(dt);
    this.statusLabel.setState(state);
    this.statusLabel.setTask(this.agent.currentTask);
    this.updateOverlayPositions();
  }

  setReducedMotion(reducedMotion: boolean) {
    this.reducedMotion = reducedMotion;
    if (reducedMotion) this.wakeFromRest();
  }

  wakeFromRest() {
    this.idleElapsed = 0;
    this.nextBehaviorAt = 8 + ((this.behaviorSeed + Math.floor(performance.now() / 1000)) % 9);
    this.spineChar?.resumeState(this.agent.state);
  }

  private updateOverlayPositions() {
    const crownTopY = this.useSpine && this.spineChar ? this.spineChar.getHeadOffsetY() : -58;
    this.statusLabel.layout(crownTopY);
    const labelTopY = this.statusLabel.getLabelTopY(crownTopY);
    const gapAboveLabel = 4;
    const bubbleExtraDown = 10;
    this.bubble.position.set(0, labelTopY - gapAboveLabel - Bubble.TAIL_TIP_Y + bubbleExtraDown);
  }

  private syncVisual() {
    this.statusLabel.setName(this.agent.name);
    this.statusLabel.setState(this.agent.state);
    this.statusLabel.setTask(this.agent.currentTask);
    if (this.agent.bubbleText) {
      this.bubble.show(this.agent.bubbleText);
    }
    if (this.useSpine && this.spineChar) {
      this.spineChar.playState(this.agent.state, this.agent.customAnimation);
      this.spineChar.setFacing(this.agent.facing);
      this.spineChar.setViewFacing(this.agent.viewFacing ?? "front");
      this.spineChar.setAgentColor(this.agent.color);
    } else {
      this.drawFallbackBody(this.agent.state, 0);
    }
    this.updateOverlayPositions();
  }

  private initFallbackGraphics() {
    this.fallbackBody = new Graphics();
    this.fallbackScarf = new Graphics();
    this.addChild(this.fallbackBody, this.fallbackScarf);
    this.useSpine = false;
  }

  private updatePresentation(state: AgentState, dt: number) {
    if (this.reducedMotion || state !== "idle") {
      this.idleElapsed = 0;
      return;
    }

    this.idleElapsed += dt;
    if (this.idleElapsed < this.nextBehaviorAt) return;
    this.idleElapsed = 0;
    this.nextBehaviorAt = 10 + ((this.behaviorSeed + Math.floor(performance.now() / 1000)) % 8);
    this.spineChar?.playFirstAvailable(this.profile.idleActions);
  }

  private mountRoleAccessories() {
    const graphics = this.roleAccessories;
    graphics.clear();
    this.profile.accessorySlots.slice(0, 2).forEach((accessory, index) => {
      const x = index === 0 ? -29 : 29;
      const y = -8 - index * 6;
      graphics.roundRect(x - 8, y - 7, 16, 14, 4);
      graphics.fill({ color: this.profile.accentColor, alpha: 0.9 });
      graphics.stroke({ color: 0xffffff, width: 1.2, alpha: 0.9 });

      if (accessory.includes("glasses") || accessory.includes("monitors")) {
        graphics.rect(x - 5, y - 3, 4, 5);
        graphics.rect(x + 1, y - 3, 4, 5);
        graphics.fill(0xffffff);
      } else if (accessory.includes("headset") || accessory.includes("compass")) {
        graphics.circle(x, y, 4);
        graphics.stroke({ color: 0xffffff, width: 1.5, alpha: 1 });
      } else if (accessory.includes("chart") || accessory.includes("board")) {
        graphics.moveTo(x - 5, y + 3);
        graphics.lineTo(x - 1, y);
        graphics.lineTo(x + 2, y + 1);
        graphics.lineTo(x + 5, y - 4);
        graphics.stroke({ color: 0xffffff, width: 1.5, alpha: 1 });
      } else {
        graphics.moveTo(x - 4, y + 3);
        graphics.lineTo(x + 4, y - 3);
        graphics.stroke({ color: 0xffffff, width: 1.7, alpha: 1 });
      }
    });
  }

  private drawFallbackBody(state: AgentState, bob: number) {
    if (!this.fallbackBody || !this.fallbackScarf) return;

    const facing = this.agent.facing;
    const g = this.fallbackBody;
    const s = this.fallbackScarf;
    g.clear();
    s.clear();

    const bounce =
      state === "walking" ? Math.sin(this.walkPhase) * 2 : state === "working" ? Math.sin(this.walkPhase * 2) * 1 : bob;

    // shadow
    g.ellipse(0, 16 + bounce, 14, 4);
    g.fill({ color: 0x000000, alpha: 0.1 });

    // legs / pants
    const legSwing = state === "walking" ? Math.sin(this.walkPhase) * 3 : 0;
    g.roundRect(-9, 6 + bounce + legSwing, 7, 12, 2);
    g.fill(0x3a3f4a);
    g.roundRect(2, 6 + bounce - legSwing, 7, 12, 2);
    g.fill(0x3a3f4a);

    // shirt body
    g.roundRect(-11, -8 + bounce, 22, 18, 4);
    g.fill(0xf8f8f6);
    g.roundRect(-7, -8 + bounce, 14, 4, 2);
    g.fill(0xe8e8e6);

    // head
    g.circle(facing * 1, -20 + bounce, 10);
    g.fill(0xffe0c4);
    g.roundRect(facing * 1 - 10, -28 + bounce, 20, 8, 3);
    g.fill(0x2a2a30);

    // typing arm when working
    if (state === "working") {
      const armY = -4 + bounce + Math.sin(this.walkPhase * 3) * 2;
      g.roundRect(facing * 12, armY, 8, 4, 2);
      g.fill(0xf8f8f6);
    }

    // thinking dots
    if (state === "thinking") {
      for (let i = 0; i < 3; i++) {
        g.circle(14 + i * 6, -34 + bounce, 2);
        g.fill({ color: 0x9b6dd7, alpha: i <= Math.floor(this.walkPhase) % 3 ? 1 : 0.3 });
      }
    }

    // badge / 工牌
    s.roundRect(facing * 4 - 5, -2 + bounce, 10, 8, 2);
    s.fill(this.agent.color);
  }
}

function stableBehaviorSeed(agentId: string) {
  let hash = 2166136261;
  for (const character of agentId) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}
