import { Loader } from "@/components/ui/loader";
import { TableCell, TableRow } from "@/components/ui/table";

type TableLoadingRowProps = {
  colSpan: number;
  label?: string;
};

export function TableLoadingRow({ colSpan, label = "列表加载中" }: TableLoadingRowProps) {
  return (
    <TableRow>
      <TableCell className="h-28 text-center" colSpan={colSpan}>
        <div className="inline-flex items-center gap-2 text-muted-foreground text-sm">
          <Loader />
          {label}
        </div>
      </TableCell>
    </TableRow>
  );
}

export function ProcessingState({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <Loader size={14} />
      {label}
    </span>
  );
}
