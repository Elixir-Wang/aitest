"use client";

import * as React from "react";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ChevronRight, PlusCircleIcon } from "lucide-react";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from "@/components/ui/sidebar";
import type { NavGroup, NavMainItem } from "@/navigation/sidebar/sidebar-items";
import { useAuthStore } from "@/stores/auth-store";
import { getProjectScopedUrl, useProjectContextStore } from "@/stores/project-context-store";

const ROLE_RANK: Record<"admin" | "tester" | "guest", number> = {
  admin: 3,
  tester: 2,
  guest: 1,
};

function hasRequiredRole(
  userRole: "admin" | "tester" | "guest" | undefined,
  requiredRole: "admin" | "tester" | "guest" | undefined,
): boolean {
  if (!requiredRole) return true;
  if (!userRole) return false;
  return ROLE_RANK[userRole] >= ROLE_RANK[requiredRole];
}

interface NavMainProps {
  readonly items: readonly NavGroup[];
}

const IsComingSoon = () => (
  <span className="ml-auto rounded-md bg-muted px-2 py-1 text-muted-foreground text-xs">Soon</span>
);

const NavItemExpanded = ({
  item,
  isActive,
  isSubmenuOpen,
  resolveUrl,
}: {
  item: NavMainItem;
  isActive: (url: string, subItems?: NavMainItem["subItems"]) => boolean;
  isSubmenuOpen: (subItems?: NavMainItem["subItems"]) => boolean;
  resolveUrl: (item: Pick<NavMainItem, "projectScoped" | "url">) => string;
}) => {
  const href = resolveUrl(item);

  return (
    <Collapsible key={item.title} asChild defaultOpen={isSubmenuOpen(item.subItems)} className="group/collapsible">
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          {item.subItems ? (
            <SidebarMenuButton disabled={item.comingSoon} isActive={isActive(href, item.subItems)} tooltip={item.title}>
              {item.icon && <item.icon />}
              <span>{item.title}</span>
              {item.comingSoon && <IsComingSoon />}
              <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
            </SidebarMenuButton>
          ) : (
            <SidebarMenuButton asChild aria-disabled={item.comingSoon} isActive={isActive(href)} tooltip={item.title}>
              <Link prefetch={false} href={href} target={item.newTab ? "_blank" : undefined}>
                {item.icon && <item.icon />}
                <span>{item.title}</span>
                {item.comingSoon && <IsComingSoon />}
              </Link>
            </SidebarMenuButton>
          )}
        </CollapsibleTrigger>
        {item.subItems && (
          <CollapsibleContent>
            <SidebarMenuSub>
              {item.subItems.map((subItem) => (
                <SidebarMenuSubItem key={subItem.title}>
                  <SidebarMenuSubButton
                    aria-disabled={subItem.comingSoon}
                    isActive={isActive(resolveUrl(subItem))}
                    asChild
                  >
                    <Link
                      aria-disabled={subItem.comingSoon}
                      prefetch={false}
                      href={resolveUrl(subItem)}
                      target={subItem.newTab ? "_blank" : undefined}
                      onClick={(event) => {
                        if (subItem.comingSoon) {
                          event.preventDefault();
                        }
                      }}
                    >
                      {subItem.icon && <subItem.icon />}
                      <span>{subItem.title}</span>
                      {subItem.comingSoon && <IsComingSoon />}
                    </Link>
                  </SidebarMenuSubButton>
                </SidebarMenuSubItem>
              ))}
            </SidebarMenuSub>
          </CollapsibleContent>
        )}
      </SidebarMenuItem>
    </Collapsible>
  );
};

const NavItemCollapsed = ({
  item,
  isActive,
  resolveUrl,
}: {
  item: NavMainItem;
  isActive: (url: string, subItems?: NavMainItem["subItems"]) => boolean;
  resolveUrl: (item: Pick<NavMainItem, "projectScoped" | "url">) => string;
}) => {
  const href = resolveUrl(item);

  return (
    <SidebarMenuItem key={item.title}>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <SidebarMenuButton disabled={item.comingSoon} tooltip={item.title} isActive={isActive(href, item.subItems)}>
            {item.icon && <item.icon />}
            <span>{item.title}</span>
            <ChevronRight />
          </SidebarMenuButton>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-50 space-y-1" side="right" align="start">
          {item.subItems?.map((subItem) => (
            <DropdownMenuItem key={subItem.title} asChild>
              <SidebarMenuSubButton
                key={subItem.title}
                asChild
                className="focus-visible:ring-0"
                aria-disabled={subItem.comingSoon}
                isActive={isActive(resolveUrl(subItem))}
              >
                <Link
                  aria-disabled={subItem.comingSoon}
                  prefetch={false}
                  href={resolveUrl(subItem)}
                  target={subItem.newTab ? "_blank" : undefined}
                  onClick={(event) => {
                    if (subItem.comingSoon) {
                      event.preventDefault();
                    }
                  }}
                >
                  {subItem.icon && <subItem.icon className="[&>svg]:text-sidebar-foreground" />}
                  <span>{subItem.title}</span>
                  {subItem.comingSoon && <IsComingSoon />}
                </Link>
              </SidebarMenuSubButton>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </SidebarMenuItem>
  );
};

export function NavMain({ items }: NavMainProps) {
  const path = usePathname();
  const { state, isMobile } = useSidebar();
  const { currentProjectId, hydrate, scope } = useProjectContextStore();
  const user = useAuthStore((s) => s.user);

  React.useEffect(() => {
    hydrate();
  }, [hydrate]);

  const resolveUrl = (item: Pick<NavMainItem, "projectScoped" | "url">) => {
    if (!item.projectScoped) {
      return item.url;
    }

    return getProjectScopedUrl(item.url, currentProjectId, scope);
  };

  const isItemActive = (url: string, subItems?: NavMainItem["subItems"]) => {
    if (subItems?.length) {
      return subItems.some((sub) => path === resolveUrl(sub));
    }
    return path === url;
  };

  const isSubmenuOpen = (subItems?: NavMainItem["subItems"]) => {
    return subItems?.some((sub) => path === resolveUrl(sub)) ?? false;
  };

  return (
    <>
      <SidebarGroup>
        <SidebarGroupContent className="flex flex-col gap-2">
          <SidebarMenu>
            <SidebarMenuItem className="flex items-center gap-2">
              <SidebarMenuButton
                tooltip="Quick Create"
                className="min-w-8 bg-primary text-primary-foreground duration-200 ease-linear hover:bg-primary/90 hover:text-primary-foreground active:bg-primary/90 active:text-primary-foreground"
              >
                <PlusCircleIcon />
                <span>新建任务</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
      {items.map((group) => {
        const visibleItems = group.items.filter((item) => hasRequiredRole(user?.role, item.requiredRole));
        if (visibleItems.length === 0) return null;
        return (
          <SidebarGroup key={group.id}>
            {group.label && <SidebarGroupLabel>{group.label}</SidebarGroupLabel>}
            <SidebarGroupContent className="flex flex-col gap-2">
              <SidebarMenu>
                {visibleItems.map((item) => {
                  if (state === "collapsed" && !isMobile) {
                    // If no subItems, just render the button as a link
                    if (!item.subItems) {
                      const href = resolveUrl(item);
                      return (
                        <SidebarMenuItem key={item.title}>
                          <SidebarMenuButton
                            asChild
                            aria-disabled={item.comingSoon}
                            tooltip={item.title}
                            isActive={isItemActive(href)}
                          >
                            <Link prefetch={false} href={href} target={item.newTab ? "_blank" : undefined}>
                              {item.icon && <item.icon />}
                              <span>{item.title}</span>
                            </Link>
                          </SidebarMenuButton>
                        </SidebarMenuItem>
                      );
                    }
                    // Otherwise, render the dropdown as before
                    return (
                      <NavItemCollapsed key={item.title} item={item} isActive={isItemActive} resolveUrl={resolveUrl} />
                    );
                  }
                  // Expanded view
                  return (
                    <NavItemExpanded
                      key={item.title}
                      item={item}
                      isActive={isItemActive}
                      isSubmenuOpen={isSubmenuOpen}
                      resolveUrl={resolveUrl}
                    />
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        );
      })}
    </>
  );
}
