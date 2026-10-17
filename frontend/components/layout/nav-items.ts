import { FileSearch, FileText, FolderOpen, History, LayoutDashboard, Settings, type LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/library", label: "Research Library", icon: FolderOpen },
  { href: "/verify", label: "Verify a Claim", icon: FileSearch },
  { href: "/investigations", label: "Investigations", icon: History },
  { href: "/reports", label: "Evidence Reports", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];
