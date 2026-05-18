import React, { useState } from "react";
import {
  BarChart3,
  CalendarDays,
  Dumbbell,
  LayoutDashboard,
  Menu,
  Settings,
  Sparkles,
  TrendingUp,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { THEME } from "../theme";
import type { AppTab } from "../types/navigation";

type SideNavProps = {
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  subtitle?: string;
  children?: React.ReactNode;
};

const NAV_ITEMS: Array<{ tab: AppTab; label: string; Icon: LucideIcon }> = [
  { tab: "dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { tab: "recent-analysis", label: "Recent Analysis", Icon: BarChart3 },
  { tab: "clients", label: "Clients", Icon: UsersRound },
  { tab: "sessions", label: "Sessions", Icon: CalendarDays },
  { tab: "insights", label: "Insights", Icon: TrendingUp },
  { tab: "settings", label: "Settings", Icon: Settings },
];

export default function SideNav({
  activeTab,
  onTabChange,
  subtitle = "Coach Workspace",
  children,
}: SideNavProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <aside
      style={isOpen ? styles.sidebar : styles.sidebarCollapsed}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      <div style={isOpen ? styles.brandRow : styles.brandRowCollapsed}>
        <button
          type="button"
          style={styles.menuButton}
          onClick={() => setIsOpen((current) => !current)}
          onFocus={() => setIsOpen(true)}
          aria-label={isOpen ? "Collapse navigation" : "Open navigation"}
          title={isOpen ? "Collapse navigation" : "Open navigation"}
        >
          <Menu size={18} strokeWidth={2.4} />
        </button>

        {isOpen ? (
          <div style={styles.brandText}>
            <div style={styles.brandTitle}>Vectra</div>
            <div style={styles.brandSubtitle}><Sparkles size={12} /> {subtitle}</div>
          </div>
        ) : null}
      </div>

      {isOpen && children ? <div style={styles.sideContent}>{children}</div> : null}

      <nav style={styles.navSection} aria-label="Primary navigation">
        {NAV_ITEMS.map((item) => {
          const isActive = activeTab === item.tab;
          const Icon = item.Icon;
          return (
            <button
              key={item.tab}
              type="button"
              style={getNavItemStyle(isActive, isOpen)}
              onClick={() => onTabChange(item.tab)}
              title={item.label}
              aria-label={item.label}
            >
              <Icon size={THEME.icons.md} strokeWidth={2.2} />
              {isOpen ? <span>{item.label}</span> : null}
            </button>
          );
        })}
      </nav>
      {isOpen ? (
        <div style={styles.navFooter}>
          <Dumbbell size={16} />
          Movement-first coaching
        </div>
      ) : null}
    </aside>
  );
}

function getNavItemStyle(isActive: boolean, isOpen: boolean): React.CSSProperties {
  const base = isActive ? styles.navItemActive : styles.navItem;

  return {
    ...base,
    justifyContent: isOpen ? "flex-start" : "center",
    padding: isOpen ? "10px 12px" : "10px 0",
    textAlign: isOpen ? "left" : "center",
    gap: isOpen ? 10 : 0,
  };
}

const styles: Record<string, React.CSSProperties> = {
  sidebar: {
    width: 280,
    background: THEME.gradients.navy,
    borderRight: `1px solid rgba(255,255,255,0.08)`,
    padding: 20,
    boxSizing: "border-box",
    transition: "width 180ms ease",
    flexShrink: 0,
  },
  sidebarCollapsed: {
    width: 76,
    background: THEME.gradients.navy,
    borderRight: `1px solid rgba(255,255,255,0.08)`,
    padding: "20px 12px",
    boxSizing: "border-box",
    transition: "width 180ms ease",
    flexShrink: 0,
  },
  brandRow: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  brandRowCollapsed: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  menuButton: {
    width: 40,
    height: 40,
    borderRadius: THEME.radii.sm,
    border: "1px solid rgba(255,255,255,0.18)",
    backgroundColor: THEME.colors.primary,
    color: THEME.colors.white,
    display: "inline-flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    cursor: "pointer",
    flexShrink: 0,
  },
  brandText: {
    minWidth: 0,
  },
  brandTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: THEME.colors.white,
  },
  brandSubtitle: {
    display: "flex",
    alignItems: "center",
    gap: 5,
    fontSize: 12,
    color: "#a8b8d6",
  },
  sideContent: {
    marginTop: 24,
  },
  navSection: {
    marginTop: 24,
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  navItemActive: {
    minHeight: 40,
    borderRadius: THEME.radii.sm,
    backgroundColor: "rgba(255,255,255,0.09)",
    color: THEME.colors.white,
    fontWeight: 700,
    border: "1px solid rgba(255,255,255,0.16)",
    boxShadow: `inset 4px 0 0 ${THEME.colors.primary}`,
    display: "flex",
    alignItems: "center",
    cursor: "pointer",
    width: "100%",
  },
  navItem: {
    minHeight: 40,
    borderRadius: THEME.radii.sm,
    color: "#a8b8d6",
    border: "1px solid transparent",
    backgroundColor: "transparent",
    display: "flex",
    alignItems: "center",
    cursor: "pointer",
    width: "100%",
    fontWeight: 700,
  },
  navFooter: {
    marginTop: 24,
    display: "flex",
    alignItems: "center",
    gap: 8,
    color: "#a8b8d6",
    fontSize: 12,
    fontWeight: 700,
    backgroundColor: "rgba(255,255,255,0.06)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: THEME.radii.md,
    padding: 12,
  },
};
