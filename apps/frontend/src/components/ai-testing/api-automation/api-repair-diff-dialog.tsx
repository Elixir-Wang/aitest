import { Loader2 } from "lucide-react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export function ApiRepairDiffDialog({
  diff,
  error,
  loading,
  open,
  onOpenChange,
}: {
  diff: string;
  error: string;
  loading: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent className="grid h-[min(52rem,calc(100vh-2rem))] w-[calc(100vw-2rem)] max-w-none grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden p-0 sm:max-w-6xl">
        <DialogHeader className="border-b px-5 py-4 pr-14">
          <DialogTitle>候选修改 Diff</DialogTitle>
          <DialogDescription>仅展示本轮临时副本中的候选修改，批准前不会修改正式测试套件。</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 overflow-auto p-5">
          {loading ? (
            <div className="flex min-h-48 items-center justify-center text-muted-foreground text-sm">
              <Loader2 className="mr-2 size-4 animate-spin" /> 正在加载候选修改
            </div>
          ) : null}
          {!loading && error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">
              {error}
            </div>
          ) : null}
          {!loading && !error && !diff ? (
            <div className="flex min-h-48 items-center justify-center text-muted-foreground text-sm">
              本轮没有可展示的修改。
            </div>
          ) : null}
          {!loading && !error && diff ? (
            <pre className="min-h-full overflow-auto whitespace-pre rounded-lg bg-zinc-950 p-4 font-mono text-xs text-zinc-100 leading-5">
              {diff}
            </pre>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
