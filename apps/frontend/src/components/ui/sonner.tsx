"use client"

import { Toaster as Sonner, type ToasterProps } from "sonner"
import { CircleCheckIcon, InfoIcon, TriangleAlertIcon, OctagonXIcon, Loader2Icon } from "lucide-react"
import { usePreferencesStore } from "@/stores/preferences/preferences-provider"

const Toaster = ({ ...props }: ToasterProps) => {
  const theme = usePreferencesStore((state) => (state.themeMode === "dark" ? "dark" : "light"))

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      closeButton
      duration={5000}
      swipeDirections={[]}
      icons={{
        success: (
          <CircleCheckIcon className="size-4 text-green-600 dark:text-green-400" />
        ),
        info: (
          <InfoIcon className="size-4 text-muted-foreground" />
        ),
        warning: (
          <TriangleAlertIcon className="size-4 text-amber-600 dark:text-amber-400" />
        ),
        error: (
          <OctagonXIcon className="size-4 text-destructive" />
        ),
        loading: (
          <Loader2Icon className="size-4 animate-spin" />
        ),
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
      toastOptions={{
        classNames: {
          toast: "cn-toast select-text rounded-xl border pr-16 shadow-md",
          default: "bg-card border-border text-foreground",
          success: "bg-card border-green-600/50 text-foreground",
          info: "bg-card border-border text-foreground",
          warning: "bg-card border-amber-600/50 text-foreground",
          error: "bg-card border-destructive/50 text-foreground",
          title: "select-text text-xs font-medium leading-none",
          description: "select-text text-xs !text-muted-foreground",
          closeButton:
            "!right-3 !left-auto !top-1/2 !size-9 !-translate-y-1/2 ![transform:none] !rounded-md border border-transparent bg-muted/70 p-0 text-xs text-muted-foreground transition-colors after:content-['关闭'] hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 [&>svg]:hidden",
          actionButton:
            "border border-border bg-background text-foreground hover:bg-muted/10 dark:hover:bg-muted/20",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
