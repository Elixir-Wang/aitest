import { Container, Graphics, Text } from "pixi.js";

const NAME_STYLE = {
  fontFamily: "Noto Sans SC, system-ui, sans-serif",
  fontSize: 11,
  fontWeight: "600" as const,
  fill: 0x263244,
};

const TASK_STYLE = {
  fontFamily: "Noto Sans SC, system-ui, sans-serif",
  fontSize: 8.5,
  fill: 0x7a8798,
};

const STATE_COLORS: Record<string, number> = {
  idle: 0xa8b1bd,
  walking: 0x4a90d9,
  working: 0x2fba83,
  talking: 0xe8a838,
  thinking: 0x4f8df7,
};

const CARD_WIDTH = 140;
const CARD_HEIGHT = 36;
const LABEL_CENTER_Y = 76;

export class StatusLabel extends Container {
  private nameText: Text;
  private taskText: Text;
  private stateDot: Graphics;
  private cardBackground: Graphics;
  private currentState = "idle";

  constructor(name: string) {
    super();
    this.cardBackground = new Graphics();
    this.nameText = new Text({ text: name, style: NAME_STYLE });
    this.taskText = new Text({ text: "", style: TASK_STYLE });
    this.stateDot = new Graphics();
    this.addChild(this.cardBackground, this.nameText, this.taskText, this.stateDot);
    this.paintCard();
  }

  setName(name: string) {
    this.nameText.text = name;
    this.layoutContent();
  }

  setTask(task?: string) {
    this.taskText.text = task ?? "等待任务";
    this.layoutContent();
  }

  setState(state: string) {
    this.currentState = state;
    this.paintStateDot();
  }

  layout(_crownTopY: number) {
    this.position.set(0, LABEL_CENTER_Y);
  }

  getLabelTopY(_crownTopY: number): number {
    return LABEL_CENTER_Y - CARD_HEIGHT / 2;
  }

  private paintCard() {
    this.cardBackground.clear();
    this.cardBackground.roundRect(-CARD_WIDTH / 2, -CARD_HEIGHT / 2, CARD_WIDTH, CARD_HEIGHT, 6);
    this.cardBackground.fill({ color: 0xffffff, alpha: 0.96 });
    this.cardBackground.stroke({ color: 0xdce4ee, width: 1, alpha: 0.95 });
    this.layoutContent();
  }

  private layoutContent() {
    const left = -CARD_WIDTH / 2 + 10;
    this.nameText.anchor.set(0, 0.5);
    this.nameText.position.set(left, -7);
    this.taskText.anchor.set(0, 0.5);
    this.taskText.position.set(left, 9);
    this.paintStateDot();
  }

  private paintStateDot() {
    const color = STATE_COLORS[this.currentState] ?? STATE_COLORS.idle;
    this.stateDot.clear();
    this.stateDot.circle(CARD_WIDTH / 2 - 12, -8, 3.5);
    this.stateDot.fill(color);
  }
}
