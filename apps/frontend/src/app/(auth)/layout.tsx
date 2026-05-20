import type { ReactNode } from "react";

export default function Layout({ children }: Readonly<{ children: ReactNode }>) {
  return <main className="min-h-dvh">{children}</main>;
}
