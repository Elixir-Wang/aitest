import { Users } from "lucide-react";

export function LoadProfileRail({
  users,
  spawnRate,
  measurementSeconds,
}: {
  users: number;
  spawnRate: number;
  measurementSeconds: number;
}) {
  const rampSeconds = spawnRate > 0 ? Math.ceil(users / spawnRate) : 0;
  const total = Math.max(rampSeconds + measurementSeconds, 1);
  const rampWidth = Math.min(Math.max((rampSeconds / total) * 100, 12), 55);

  return (
    <div className="border-y py-4">
      <div className="mb-3 flex items-center justify-between gap-3 text-xs">
        <span className="flex items-center gap-1.5 font-medium">
          <Users className="size-3.5" />
          {users} 个并发用户
        </span>
        <span className="text-muted-foreground">预计总时长 {formatDuration(rampSeconds + measurementSeconds)}</span>
      </div>
      <div className="flex h-8 overflow-hidden rounded-md border bg-muted/40">
        <div
          className="flex min-w-24 items-center justify-center bg-sky-100 px-2 text-sky-800 text-xs dark:bg-sky-950 dark:text-sky-200"
          style={{ width: `${rampWidth}%` }}
        >
          爬升 {formatDuration(rampSeconds)}
        </div>
        <div className="flex flex-1 items-center justify-center bg-emerald-100 px-2 text-emerald-800 text-xs dark:bg-emerald-950 dark:text-emerald-200">
          正式测量 {formatDuration(measurementSeconds)}
        </div>
      </div>
      <p className="mt-2 text-muted-foreground text-xs">性能目标只使用正式测量区间的数据。</p>
    </div>
  );
}

function formatDuration(seconds: number) {
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes} 分 ${rest} 秒` : `${minutes} 分`;
}
