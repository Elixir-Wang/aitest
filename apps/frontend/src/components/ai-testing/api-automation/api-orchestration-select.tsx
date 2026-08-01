"use client";

import type { ComponentProps } from "react";

import {
  Select as BaseSelect,
  SelectContent as BaseSelectContent,
  SelectGroup,
  SelectItem as BaseSelectItem,
  SelectLabel,
  SelectTrigger as BaseSelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Select as AnimatedSelect, SelectOption } from "@/components/ui/animated-select-1";
import { cn } from "@/lib/utils";

function Select(props: ComponentProps<typeof BaseSelect>) {
  return <BaseSelect {...props} />;
}

function SelectTrigger({ className, ...props }: ComponentProps<typeof BaseSelectTrigger>) {
  return (
    <BaseSelectTrigger
      className={cn(
        "h-8 w-full min-w-44 cursor-pointer rounded-lg border-input bg-transparent px-2.5 py-1 text-left text-sm text-foreground hover:bg-muted data-[state=open]:[&_svg]:rotate-180 [&_svg]:transition-transform [&_svg]:duration-200 dark:bg-input/30 dark:hover:bg-input/50",
        className,
      )}
      {...props}
    />
  );
}

function SelectContent({
  className,
  position = "popper",
  sideOffset = 8,
  ...props
}: ComponentProps<typeof BaseSelectContent>) {
  return (
    <BaseSelectContent
      className={cn(
        "z-[100] rounded-lg border border-border bg-popover py-0.5 text-sm text-popover-foreground shadow-sm ring-0",
        className,
      )}
      position={position}
      sideOffset={sideOffset}
      {...props}
    />
  );
}

function SelectItem({ className, ...props }: ComponentProps<typeof BaseSelectItem>) {
  return (
    <BaseSelectItem
      className={cn(
        "cursor-pointer rounded-md px-2.5 py-1 text-sm leading-normal transition-colors duration-200 hover:bg-muted [&>span:first-child]:hidden",
        className,
      )}
      {...props}
    />
  );
}

export {
  AnimatedSelect,
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectOption,
  SelectTrigger,
  SelectValue,
};
