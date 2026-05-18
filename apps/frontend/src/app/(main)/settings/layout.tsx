import type { ReactNode } from "react";

import { WorkspaceShell } from "@/components/ai-testing/workspace-shell";

export default async function Layout({ children }: Readonly<{ children: ReactNode }>) {
  return <WorkspaceShell>{children}</WorkspaceShell>;
}
