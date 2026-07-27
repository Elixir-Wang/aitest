import { Container, FillGradient, Graphics, Sprite } from "pixi.js";

import { getOfficeChairTexture } from "@/scene/assets/loadOfficeAssets";
import { SEAT_OFFSET_Y } from "@/scene/layout/officeLayout";
import { computeChairLayerZ, computeDeskLayerZ } from "@/scene/systems/deskDepthSort";
import type { Desk } from "@/types/agent";

const STYLE = {
  shadow: { color: 0x3d4f6e, alpha: 0.1 },
  deskTop: 0xfaf8f4,
  deskEdge: 0xe8e0d4,
  deskStroke: 0xd8d0c4,
  chairDark: 0x556b7d,
  chair: 0x7a8fa3,
  chairWheel: 0x3d4a56,
  monitor: 0x2e3238,
  screenTop: 0x7ec8ff,
  screenBottom: 0x4a8fd9,
  keyboard: 0xeeedea,
  keyboardStroke: 0xd0ccc4,
  mouse: 0xf5f4f1,
} as const;

const CHAIR_BASE_WIDTH = 104;
const CHAIR_ANCHOR_Y = 0.36;
const CHAIR_TARGET_WIDTH = CHAIR_BASE_WIDTH / 2;
const CHAIR_POSITION_Y = 10;

const CHAIR_DEPTH_AHEAD = 0;

export class DeskEntity {
  readonly deskId: string;
  readonly shadowGfx = new Graphics();
  readonly deskLayer = new Container();
  readonly chairLayer = new Container();
  readonly occupiedIndicator = new Graphics();

  private desk: Desk;

  constructor(desk: Desk) {
    this.deskId = desk.id;
    this.desk = desk;

    for (const part of [this.shadowGfx, this.deskLayer, this.chairLayer, this.occupiedIndicator]) {
      part.position.set(desk.x, desk.y);
      part.scale.set(desk.visualScale ?? 1);
    }

    this.drawShadow();
    this.mountSprites();
  }

  /** 素材晚到或 HMR 后可重新挂载 PNG */
  remountSprites() {
    this.deskLayer.removeChildren();
    this.chairLayer.removeChildren();
    this.mountSprites();
  }

  updateDepthZ(agentPositions: { x: number; y: number }[]) {
    const deskZ = computeDeskLayerZ(this.desk, agentPositions);
    const chairZ = computeChairLayerZ(this.desk, agentPositions, CHAIR_DEPTH_AHEAD);
    this.deskLayer.zIndex = deskZ;
    this.shadowGfx.zIndex = chairZ - 0.5;
    this.chairLayer.zIndex = chairZ;
    this.occupiedIndicator.zIndex = chairZ + 0.5;
  }

  setOccupied(occupied: boolean) {
    this.occupiedIndicator.clear();
    void occupied;
  }

  getSeatPosition() {
    return { x: this.desk.seatX, y: this.desk.seatY };
  }

  destroy() {
    for (const part of [this.shadowGfx, this.deskLayer, this.chairLayer, this.occupiedIndicator]) {
      part.removeFromParent();
      part.destroy({ children: true });
    }
  }

  private mountSprites() {
    const chairTex = getOfficeChairTexture();
    if (this.desk.variant === "executive") {
      this.drawExecutiveDesk();
      this.drawExecutiveChair();
      return;
    }

    this.drawStandardDesk();
    if (chairTex) {
      const chair = new Sprite(chairTex);
      chair.anchor.set(0.5, CHAIR_ANCHOR_Y);
      chair.position.set(-32, CHAIR_POSITION_Y);
      chair.scale.set(CHAIR_TARGET_WIDTH / chairTex.width);
      this.chairLayer.addChild(chair);
    } else {
      this.drawChairFallback(-32);
    }
  }

  private drawStandardDesk() {
    const g = new Graphics();
    const monitorX = 34;

    g.ellipse(0, 45, 72, 15);
    g.fill({ color: 0x45566b, alpha: 0.1 });
    g.roundRect(-68, -7, 136, 34, 7);
    g.fill(0xf9faf9);
    g.stroke({ color: 0xd7dde2, width: 1.2 });
    g.roundRect(-66, 23, 132, 7, 3);
    g.fill(0xdfe4e8);
    g.roundRect(-60, 29, 9, 48, 3);
    g.roundRect(51, 29, 9, 48, 3);
    g.fill(0xcbd2d8);
    g.roundRect(34, 29, 26, 43, 3);
    g.fill(0xe7eaed);
    g.stroke({ color: 0xcbd2d8, width: 1 });

    this.drawMonitor(g, monitorX, 0.86);
    g.roundRect(monitorX - 20, 1, 39, 7, 3);
    g.fill(STYLE.keyboard);
    g.ellipse(monitorX + 28, 5, 4, 6);
    g.fill(STYLE.mouse);
    this.deskLayer.addChild(g);
  }

  private drawExecutiveDesk() {
    const g = new Graphics();
    const monitorX = 48;

    g.ellipse(0, 54, 128, 22);
    g.fill({ color: 0x26364a, alpha: 0.14 });
    g.roundRect(-108, -8, 216, 48, 12);
    g.fill(0xf5eee3);
    g.stroke({ color: 0xc8aa7a, width: 2, alpha: 0.85 });
    g.roundRect(-104, 32, 208, 10, 5);
    g.fill(0x8a6038);
    g.roundRect(-96, 40, 18, 58, 5);
    g.roundRect(78, 40, 18, 58, 5);
    g.fill(0x6d4b30);

    g.roundRect(monitorX - 30, -58, 60, 40, 7);
    g.fill(0x182232);
    g.roundRect(monitorX - 25, -53, 50, 30, 5);
    g.fill(
      new FillGradient({
        type: "linear",
        start: { x: 0, y: 0 },
        end: { x: 0, y: 1 },
        colorStops: [
          { offset: 0, color: 0x6fc8ff },
          { offset: 1, color: 0x285ca8 },
        ],
        textureSpace: "local",
      }),
    );
    g.roundRect(monitorX - 3, -18, 6, 15, 3);
    g.fill(0x4a4f57);
    g.roundRect(monitorX - 25, 2, 50, 9, 4);
    g.fill(0xdad7d1);
    g.ellipse(monitorX + 38, 7, 6, 8);
    g.fill(0xf4f1eb);

    g.roundRect(-96, -3, 50, 11, 5);
    g.fill(0xe7d4b5);
    g.roundRect(-88, -22, 34, 20, 4);
    g.fill(0x274867);
    g.stroke({ color: 0xd5b56d, width: 1.5 });

    this.drawPlant(g, -132, 28);
    this.deskLayer.addChild(g);
  }

  private drawExecutiveChair() {
    const g = new Graphics();
    g.roundRect(-82, -48, 58, 70, 19);
    g.fill(0x26394d);
    g.stroke({ color: 0x142333, width: 2 });
    g.roundRect(-78, 10, 50, 18, 8);
    g.fill(0x344c63);
    g.rect(-57, 26, 8, 34);
    g.fill(0x26394d);
    g.ellipse(-53, 62, 35, 8);
    g.fill({ color: 0x1d2b3a, alpha: 0.9 });
    this.chairLayer.addChild(g);
  }

  private drawMonitor(g: Graphics, monitorX: number, scale: number) {
    g.roundRect(monitorX - 25 * scale, -51 * scale, 50 * scale, 34 * scale, 5 * scale);
    g.fill(STYLE.monitor);
    g.roundRect(monitorX - 21 * scale, -47 * scale, 42 * scale, 25 * scale, 3 * scale);
    g.fill(
      new FillGradient({
        type: "linear",
        start: { x: 0, y: 0 },
        end: { x: 0, y: 1 },
        colorStops: [
          { offset: 0, color: STYLE.screenTop },
          { offset: 1, color: STYLE.screenBottom },
        ],
        textureSpace: "local",
      }),
    );
    g.roundRect(monitorX - 2.5, -17 * scale, 5, 13 * scale, 2);
    g.fill(0x626a73);
  }

  private drawPlant(g: Graphics, x: number, y: number) {
    g.roundRect(x - 12, y + 12, 24, 25, 5);
    g.fill(0xb08a62);
    g.moveTo(x, y + 12);
    g.lineTo(x, y - 34);
    g.stroke({ color: 0x47724e, width: 4 });
    for (const [leafX, leafY, rotation] of [
      [-11, -18, -0.55],
      [11, -14, 0.55],
      [-9, -3, -0.45],
      [10, 1, 0.45],
      [0, -30, 0],
    ] as const) {
      const leaf = new Graphics();
      leaf.ellipse(0, 0, 8, 17);
      leaf.fill({ color: leafY < -20 ? 0x4f8a58 : 0x63a56b, alpha: 0.98 });
      leaf.position.set(x + leafX, y + leafY);
      leaf.rotation = rotation;
      this.deskLayer.addChild(leaf);
    }
  }

  private drawShadow() {
    const g = this.shadowGfx;
    g.clear();
    g.ellipse(0, 45, 72, 16);
    g.fill(STYLE.shadow);
  }

  private drawChairFallback(offsetX = 0) {
    const g = new Graphics();
    const seatY = 30;
    const backTop = 40;
    const backBottom = 58;
    const baseY = 64;

    g.ellipse(0, baseY, 30, 11);
    g.fill(STYLE.chairDark);
    for (let i = 0; i < 5; i++) {
      const a = (i / 5) * Math.PI * 2 - Math.PI / 2;
      g.circle(Math.cos(a) * 24, baseY + Math.sin(a) * 6, 3.5);
      g.fill(STYLE.chairWheel);
    }
    g.roundRect(-24, backTop, 48, backBottom - backTop, 14);
    g.fill(STYLE.chair);
    g.roundRect(-22, seatY, 44, 14, 8);
    g.fill(STYLE.chair);

    g.position.set(offsetX, SEAT_OFFSET_Y - 36);
    this.chairLayer.addChild(g);
  }
}
