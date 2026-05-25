import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const bannerVariants = cva("relative w-full text-sm", {
  variants: {
    variant: {
      default: "border border-border bg-background text-foreground",
      muted: "border border-transparent bg-muted text-foreground",
      warning:
        "border border-amber-300/70 bg-amber-50 text-amber-950 dark:border-amber-800/60 dark:bg-amber-950/30 dark:text-amber-100",
      destructive:
        "border border-destructive/30 bg-destructive/10 text-destructive",
      border: "border-border border-b bg-background text-foreground",
    },
    size: {
      sm: "px-3 py-2",
      default: "px-4 py-3",
      lg: "px-4 py-4",
    },
    rounded: {
      none: "",
      default: "rounded-lg",
    },
  },
  defaultVariants: {
    variant: "default",
    size: "default",
    rounded: "none",
  },
})

interface BannerProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof bannerVariants> {
  action?: React.ReactNode
  icon?: React.ReactNode
  isClosable?: boolean
  layout?: "row" | "center" | "complex"
  onClose?: () => void
}

function Banner({
  action,
  children,
  className,
  icon,
  isClosable = false,
  layout = "row",
  onClose,
  rounded,
  size,
  variant,
  ...props
}: BannerProps) {
  return (
    <div
      className={cn(bannerVariants({ variant, size, rounded }), className)}
      data-slot="banner"
      {...props}
    >
      <div
        className={cn(
          "flex gap-3",
          layout === "center" && "justify-center",
          layout === "complex" && "flex-col md:flex-row md:items-center",
        )}
      >
        {icon ? (
          <div className="mt-0.5 flex shrink-0 items-start text-current md:mt-0">
            {icon}
          </div>
        ) : null}
        <div
          className={cn(
            "min-w-0 flex-1",
            layout === "row" && "flex items-center justify-between gap-3",
            layout === "center" && "flex justify-center",
            layout === "complex" &&
              "flex flex-col justify-between gap-3 md:flex-row md:items-center",
          )}
        >
          {children}
        </div>
        {action || isClosable ? (
          <div className="flex shrink-0 items-center gap-2">
            {action}
            {isClosable ? (
              <Button
                aria-label="关闭提示"
                className="-my-1 size-7 p-0 hover:bg-black/5 dark:hover:bg-white/10"
                onClick={onClose}
                size="icon-sm"
                type="button"
                variant="ghost"
              >
                <X className="size-4 opacity-70" />
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}

export { Banner, type BannerProps }
