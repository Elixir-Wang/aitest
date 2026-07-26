import type { AgentEntity } from "@/scene/entities/AgentEntity";

export type WalkPoint = { x: number; y: number };

const ARRIVAL_EPSILON = 0.5;

/** Moves walking entities along their queued world-space waypoints. */
export class MovementSystem {
  constructor(private readonly speed = 82) {}

  start(entity: AgentEntity, path: WalkPoint[]) {
    const normalizedPath = path.filter((point, index) => {
      if (index > 0) {
        const previous = path[index - 1];
        return previous.x !== point.x || previous.y !== point.y;
      }
      return entity.position.x !== point.x || entity.position.y !== point.y;
    });

    if (normalizedPath.length === 0) return false;

    const first = normalizedPath[0];
    entity.apply({
      state: "walking",
      walkPath: normalizedPath,
      walkPathIndex: 0,
      targetX: first.x,
      targetY: first.y,
    });
    return true;
  }

  cancel(entity: AgentEntity) {
    entity.apply({
      targetX: undefined,
      targetY: undefined,
      walkPath: undefined,
      walkPathIndex: undefined,
    });
  }

  update(entities: Map<string, AgentEntity>, dt: number) {
    const arrived: AgentEntity[] = [];

    for (const entity of entities.values()) {
      if (entity.data.state !== "walking") continue;
      if (this.advance(entity, this.speed * dt)) arrived.push(entity);
    }

    return arrived;
  }

  private advance(entity: AgentEntity, distanceBudget: number) {
    const path = entity.data.walkPath;
    if (!path?.length) return true;

    let pathIndex = entity.data.walkPathIndex ?? 0;
    let remaining = distanceBudget;

    while (remaining > 0 && pathIndex < path.length) {
      const target = path[pathIndex];
      const dx = target.x - entity.position.x;
      const dy = target.y - entity.position.y;
      const distance = Math.hypot(dx, dy);

      if (distance <= Math.max(remaining, ARRIVAL_EPSILON)) {
        entity.setPosition(target.x, target.y);
        remaining = Math.max(0, remaining - distance);
        pathIndex += 1;

        const next = path[pathIndex];
        entity.apply({
          walkPathIndex: pathIndex,
          targetX: next?.x,
          targetY: next?.y,
        });
        continue;
      }

      const ratio = remaining / distance;
      entity.setPosition(entity.position.x + dx * ratio, entity.position.y + dy * ratio);
      remaining = 0;
    }

    if (pathIndex < path.length) return false;

    this.cancel(entity);
    return true;
  }
}
