import { FileSearch, FileText, FolderOpen, History, LayoutDashboard, Settings, type LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

/** Navigation grouped by the research workflow: corpus → investigation → output. */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/verify", label: "Verify a Claim", icon: FileSearch },
      { href: "/investigations", label: "Investigations", icon: History },
    ],
  },
  { label: "Corpus", items: [{ href: "/library", label: "Research Library", icon: FolderOpen }] },
  { label: "Output", items: [{ href: "/reports", label: "Evidence Reports", icon: FileText }] },
  { label: "System", items: [{ href: "/settings", label: "Settings", icon: Settings }] },
];

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);
