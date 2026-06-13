import type { ColumnDef } from "@tanstack/react-table";
import { format, parseISO } from "date-fns";
import { MoreHorizontal } from "lucide-react";

import { StatusBadge, fulfillmentStatusTone, paymentStatusTone } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import type { OrderRow } from "./schema";

function formatOrderDate(date: string) {
  return format(parseISO(date), "h:mm a, d MMM yyyy");
}

function PaymentBadge({ status }: { status: OrderRow["payment"] }) {
  return (
    <StatusBadge tone={paymentStatusTone(status)}>
      <span className="size-1.5 rounded-full bg-current" />
      {status}
    </StatusBadge>
  );
}

function FulfillmentBadge({ status }: { status: OrderRow["fulfillment"] }) {
  return (
    <StatusBadge tone={fulfillmentStatusTone(status)}>
      <span className="size-1.5 rounded-full bg-current" />
      {status}
    </StatusBadge>
  );
}

export const recentOrdersColumns: ColumnDef<OrderRow>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <div className="w-10">
        <Checkbox
          aria-label="Select all orders"
          checked={table.getIsAllPageRowsSelected() || (table.getIsSomePageRowsSelected() && "indeterminate")}
          onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        />
      </div>
    ),
    cell: ({ row }) => (
      <div className="w-10">
        <Checkbox
          aria-label={`Select order ${row.original.id}`}
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
        />
      </div>
    ),
    enableHiding: false,
    enableSorting: false,
  },
  {
    accessorKey: "id",
    header: "Order",
    cell: ({ row }) => (
      <div className="flex flex-col gap-0.5">
        <div className="font-medium leading-none">{row.original.id}</div>
        <div className="text-muted-foreground text-xs">{row.original.items}</div>
      </div>
    ),
    enableHiding: false,
  },
  {
    accessorKey: "customer",
    header: "Customer",
  },
  {
    id: "statusSummary",
    header: "Status",
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <PaymentBadge status={row.original.payment} />
        <FulfillmentBadge status={row.original.fulfillment} />
      </div>
    ),
    filterFn: (row, _columnId, value) => {
      if (value === "Needs action") {
        return (
          row.original.payment === "Pending" ||
          row.original.payment === "Refunded" ||
          row.original.fulfillment === "Unfulfilled" ||
          row.original.fulfillment === "Returned"
        );
      }

      if (value === "Unfulfilled") {
        return row.original.fulfillment === "Unfulfilled";
      }

      if (value === "Unpaid") {
        return row.original.payment === "Pending";
      }

      if (value === "Returns") {
        return row.original.payment === "Refunded" || row.original.fulfillment === "Returned";
      }

      return true;
    },
  },
  {
    accessorKey: "total",
    header: () => <div className="w-28">Total</div>,
    cell: ({ row }) => <div className="w-28 tabular-nums">{row.original.total}</div>,
  },
  {
    accessorKey: "date",
    header: () => <div className="w-44">Date</div>,
    cell: ({ row }) => <div className="w-44 text-muted-foreground">{formatOrderDate(row.original.date)}</div>,
  },
  {
    id: "actions",
    header: () => <div className="flex w-full justify-end">Actions</div>,
    cell: () => (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <div className="flex w-full justify-end">
            <Button aria-label="Open order actions" size="icon-sm" variant="ghost">
              <MoreHorizontal />
            </Button>
          </div>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="center" className="w-40">
          <DropdownMenuLabel>Order Actions</DropdownMenuLabel>
          <DropdownMenuGroup>
            <DropdownMenuItem>View order</DropdownMenuItem>
            <DropdownMenuItem>Contact customer</DropdownMenuItem>
            <DropdownMenuItem>Copy order ID</DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    ),
    enableHiding: false,
    enableSorting: false,
  },
];
