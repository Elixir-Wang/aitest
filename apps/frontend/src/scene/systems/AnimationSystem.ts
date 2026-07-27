import type { AgentEntity } from "@/scene/entities/AgentEntity";

/** 驱动 Spine 动画切换；骨骼动画自带位移，不再使用 bob */
export class AnimationSystem {
  private readonly prefersReducedMotion =
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  update(entities: Map<string, AgentEntity>, dt: number) {
    for (const entity of entities.values()) {
      entity.setReducedMotion(this.prefersReducedMotion);
      entity.updateVisuals(entity.data.state, dt);
    }
  }
}
