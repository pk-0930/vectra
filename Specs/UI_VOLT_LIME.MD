# Vectra Performance OS — Design System & UI Implementation Specification v1.0

## 1. Project Objective

Redesign the existing Vectra React web application into a premium, athletic, fast-paced fitness management platform.

Vectra is evolving from a fitness coaching application into a unified gym management and personal training SaaS.

The application will eventually support three primary experiences:

- **Gym Owner / Admin:** A sophisticated business operating system.
- **Fitness Coach / Personal Trainer:** An efficient, focused training workspace.
- **Gym Member:** An engaging environment centered on progress and achievement.

The design must establish a reusable foundation for future React web screens and React Native applications.

**Core experience philosophy:**

"The owner should feel they're operating a sophisticated business. The trainer should feel efficient and in control. The member should feel they're progressing toward something."

The design language is named **Vectra Performance OS**, based on the **Volt Performance** visual theme.

## 2. Critical Implementation Constraints

Before changing code:

1. Inspect the existing React application, project structure, styling approach, routing, components, state management, and dependencies.
2. Identify reusable existing components and working workflows.
3. Avoid unnecessary rewrites of application functionality.
4. Preserve all existing backend integrations, API calls, authentication flows, React state behavior, and business logic.
5. Do not modify database schemas, backend APIs, or infrastructure for this visual redesign.
6. Do not introduce fabricated business data, charts, statistics, sessions, subscriptions, or activity into functional screens.
7. Where a feature has no data, use a polished empty state.
8. Avoid introducing new dependencies when the existing stack already provides an appropriate solution.
9. Ensure all changes remain responsive, accessible, maintainable, and production-oriented.

The first implementation should be a UI and design-system refactor, not a gym-management feature expansion.

## 3. Design Philosophy

### 3.1 Athletic

The application should visually communicate:

- Energy
- Movement
- Speed
- Strength
- Precision
- Progress
- Performance

### 3.2 Premium

Use clean layouts, consistent spacing, controlled colors, elegant typography, and restrained visual decoration.

Avoid excessive neon, large gradients, cluttered widgets, oversized shadows, and gaming-style interfaces.

### 3.3 Data-driven

Inspired by motorsport telemetry systems:

- Performance trends
- Target versus actual performance
- Historical comparisons
- Clear status indicators
- Compact statistics
- Progress timelines
- Thresholds and reference markers

All visualized metrics must have meaningful labels, units, time ranges, and accessible alternatives.

### 3.4 Role-aware

Every role uses the same underlying visual system, but dashboards emphasize different priorities.

Admins focus on business operations.

Coaches focus on client management and training execution.

Members focus on performance, consistency, and personal achievement.

## 4. Brand Color System

### 4.1 Core Brand Tokens

| Token | Hex | Purpose |
|---|---|---|
| brand.volt | #C9FF35 | Signature athletic accent |
| brand.charcoal | #11171B | Sidebar, dark surfaces |
| brand.graphite | #1C252A | Secondary dark panels |
| brand.offWhite | #F5F6F2 | Default application background |
| brand.white | #FFFFFF | Cards and primary surfaces |
| brand.ink | #151A20 | Main light-theme text |
| brand.muted | #667085 | Secondary light-theme text |
| brand.border | #E3E7E2 | Borders and separators |
| brand.cyan | #36DCE0 | Analysis and technical visualizations |
| brand.orange | #FF814A | Selected performance highlights |

Volt lime should represent brand actions, selected states, and performance emphasis. It must not automatically represent success.

Use dedicated semantic colors for success, warning, danger, and informational states.

### 4.2 CSS Token Foundation

Create a centralized token file or equivalent token configuration.

```css
:root {
  --color-brand: #c9ff35;
  --color-brand-hover: #b8ed21;
  --color-on-brand: #11171b;

  --color-background: #f5f6f2;
  --color-surface: #ffffff;
  --color-surface-subtle: #f0f2ee;

  --color-sidebar: #11171b;
  --color-sidebar-hover: #263037;
  --color-sidebar-active: #263329;

  --color-text-primary: #151a20;
  --color-text-secondary: #667085;
  --color-text-on-dark: #f8faf9;
  --color-text-muted-dark: #adb8bd;

  --color-border: #e3e7e2;

  --color-success: #168455;
  --color-warning: #b66a13;
  --color-danger: #c73542;
  --color-info: #1668b3;

  --color-analysis: #36dce0;
  --color-performance: #ff814a;

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 18px;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;

  --sidebar-width: 248px;
  --topbar-height: 64px;
}
```

Treat these as initial design tokens. Refine semantic contrast pairs where necessary to achieve WCAG AA.

Never use bright lime text on white backgrounds or white text on lime buttons.

### 4.3 Color Usage Rules

Default workspace:

- Off-white page background.
- White cards.
- Dark headings.
- Muted descriptions.
- Subtle neutral borders.
- Lime primary actions.
- Charcoal sidebar.

Dark performance components:

- Charcoal or graphite surfaces.
- White primary numbers.
- Muted gray labels.
- Volt lime for selected progress metrics.
- Cyan for technical analysis data where distinguishable.

Never use color alone to communicate state.

## 5. Typography System

### Primary Typeface

Use Inter or Geist for application UI:

- Navigation
- Buttons
- Forms
- Tables
- Paragraphs
- Labels
- Dialogs

### Performance Typeface

Use Barlow Condensed for selected high-impact content:

- Athletic section headings
- Personal records
- Workout achievement numbers
- Large performance statistics
- Motivational banners

Use regular UI typography for complex financial metrics and dense business tables when legibility is better.

### Typography Scale

| Style | Size | Weight |
|---|---|---|
| Page title | 30–32px | 650–700 |
| Section heading | 20–22px | 600–700 |
| Card heading | 16–18px | 600 |
| Standard body | 14px | 400–500 |
| Secondary text | 12–13px | 400–500 |
| Field label | 12–13px | 550–600 |
| KPI number | 28–36px | 650–750 |
| Athletic achievement | 40–64px | 600–700 |

Use tabular numerals for financial figures, tables, timings and changing performance metrics.

Avoid displaying large paragraphs in condensed typefaces.

## 6. Layout Architecture

### 6.1 Application Shell

Build or refactor a reusable AppShell component.

Structure:

- Fixed or sticky desktop sidebar on the left.
- Main workspace on the right.
- Top navigation bar.
- Page header containing breadcrumbs, title, optional description, and contextual actions.
- Central scrollable content area.
- Consistent page padding.

Desktop sidebar width: approximately 248px.

Top navigation height: approximately 64px.

Content horizontal padding: 24–32px on desktop.

At smaller breakpoints, convert the sidebar to a collapsible drawer.

### 6.2 Sidebar

Use charcoal background.

Display:

- Vectra logo
- Optional gym/workspace selector
- Grouped navigation items
- Active navigation indicator
- Settings access
- Account menu

Navigation behavior:

- Active items have a restrained dark-lime-tinted background.
- Active icon or indicator uses volt lime.
- Inactive labels are muted light gray.
- Hover states should be subtle.
- Use consistent Lucide icon sizing and stroke widths.

Do not use large solid lime rectangles for every navigation state.

### 6.3 Top Bar

Include:

- Contextual page title or breadcrumbs
- Global search where supported
- Notification access when implemented
- Current workspace / gym
- User avatar and account menu

Do not introduce non-functional search or notification controls.

If unavailable, omit them or clearly implement them as planned UI only in a separate design-preview environment.

### 6.4 Content Grid

Use 12-column responsive CSS Grid where appropriate.

Common layouts:

- Four KPI cards across on large screens.
- Three or two cards across on medium screens.
- Single column on mobile.
- Main content with narrower secondary insight panel.
- Dense data tables with horizontal overflow and accessible controls.

Avoid filling every available region with cards.

Give important data adequate visual breathing room.

## 7. Component Design System

Build a reusable component library organized by design responsibility.

### Foundations

- AppShell
- Sidebar
- TopBar
- PageHeader
- PageContainer
- SectionHeader
- ResponsiveGrid

### Controls

- Button
- IconButton
- TextField
- SearchInput
- Select
- Checkbox
- Radio
- Toggle
- Textarea
- DatePicker
- Tabs
- DropdownMenu
- Modal
- Drawer
- Tooltip

### Data Components

- DataTable
- StatusBadge
- KPIStatCard
- TrendIndicator
- ProgressBar
- ProgressRing
- MetricComparison
- ActivityTimeline
- EmptyState
- Skeleton
- ErrorState
- ConfirmationDialog

### Fitness Components

- MemberIdentityHeader
- AthleteMetricCard
- WorkoutSessionCard
- WorkoutPlanSummary
- NutritionSummaryCard
- ProgressPhotoGallery
- TrainingConsistencyChart
- PersonalRecordCard
- FormAnalysisSummary
- AchievementCard

### Gym Operations Components — Future

- MembershipStatusCard
- SubscriptionSummary
- RenewalAlert
- PaymentSummary
- AttendanceWidget
- TrainerAssignmentCard
- GymPerformanceCard

Implement future-oriented components only when required; use this list as the planned component taxonomy.

All components must use design tokens instead of hard-coded individual styles.

## 8. Buttons and Interaction Design

### Primary Button

- Volt lime background.
- Dark charcoal text.
- Medium weight label.
- Height approximately 40–44px.
- Border radius approximately 8–10px.

Use for the page's main action, such as "Create client" or "Save plan."

### Secondary Button

- White or neutral background.
- Subtle border.
- Dark text.

### Tertiary Button

- Minimal chrome.
- Clear hover and focus states.

### Destructive Button

- Dedicated danger color.
- Confirmation where appropriate.

### Interactions

- Hover transition: approximately 150ms.
- Modal/drawer transition: approximately 180–220ms.
- Focus states must be keyboard-visible.
- Interactive elements must have appropriate touch targets.
- Avoid attention-grabbing perpetual animation.

Support `prefers-reduced-motion`.

## 9. Motorsport-Inspired Performance Visualization

This is a defining part of the Vectra design identity.

Take inspiration from racing telemetry visualization principles, not literal race-car interface decorations.

### Data Visualization Principles

1. Data must be quickly scannable.
2. Every performance value needs context.
3. Show comparisons against a baseline or target where available.
4. Use clean axes and minimal chart ornamentation.
5. Use units and descriptive labels.
6. Color should reinforce meaning, not replace labels.
7. Missing data must not be presented as zero.
8. Include accessible text summaries or tables.
9. Do not fabricate trends from a single value.

### Suggested Metrics

For gym owners:

- Membership growth
- New registrations
- Revenue over time
- Expiring memberships
- Renewal rate
- Attendance utilization
- Trainer workload

For trainers:

- Workout adherence
- Check-in completion
- Client strength progress
- Training volume
- Personal records
- Nutrition adherence
- Client goal progression

For members:

- Weekly training frequency
- Completed workouts
- Strength progression
- Personal records
- Workout streaks
- Body measurement trends
- Goal completion

### Charts

Use suitable chart types:

- Line charts for historical performance.
- Bar charts for weekly training volumes.
- Progress rings for completion goals.
- Compact sparklines for KPI trend context.
- Comparison charts for previous versus current performance.
- Timelines for workouts, sessions and check-ins.

Do not use flashy charts merely for decoration.

### Performance Metric Card Layout

Example:

```
TRAINING VOLUME           +12.6%
────────────────────────────────
12,450 KG
vs previous 4 weeks

[Subtle line chart]

TARGET: 13,000 KG
```

Charts should be driven by actual application data with explicit time ranges.

### Movement Analysis

Use the existing form analysis module as a future signature performance feature.

When suitable real data is available, visualize joint angles, movement phases, frame comparisons, and measurements alongside videos.

Never render invented biomechanical scores or conclusions.

## 10. Role-Specific UX

### Gym Admin: Command Center

Primary qualities:

- Precision
- Control
- Operational visibility
- Reliability

Prioritize:

- Active memberships
- Renewals due
- Collections and outstanding payments
- Registrations
- Attendance
- Staff operations
- Business trends

Use primarily light surfaces for readability, with selective dark performance panels.

### Trainer: Coaching Workspace

Primary qualities:

- Efficiency
- Clarity
- Speed of action
- Client context

Prioritize:

- Assigned clients
- Upcoming sessions
- Check-ins requiring review
- Workout and nutrition plans
- Progress photos
- Client activity
- Movement analysis

Use clean cards, relevant athlete visuals, and prominent next actions.

### Member: Performance Hub

Primary qualities:

- Motivation
- Achievement
- Progress
- Personal identity

Prioritize:

- Today's workout
- Training streaks
- Progress toward goals
- Personal records
- Upcoming PT sessions
- Membership status
- Achievements

May use more expressive dark panels and performance typography, while preserving usability.

All roles must share semantic color rules, typography, spacing, and interaction patterns.

## 11. Redesign Existing Vectra Screens

The current application includes:

- Sign in and sign up
- Coach dashboard
- Client list
- Client profile
- Nutrition workspace
- Workout workspace
- Form analysis
- Progress photo timeline
- Recent analysis
- Placeholder sessions, insights and settings pages

### 11.1 Authentication

Replace the generic SaaS login appearance with a premium athletic identity.

Use:

- Clear Vectra brand presentation
- Dark charcoal and volt lime
- Focused form layout
- Spacious form controls
- Optional athletic brand illustration or imagery when appropriately sourced

Keep the authentication experience simple and accessible.

Preserve the existing sign-in and sign-up functionality.

### 11.2 Coach Dashboard

Replace the current generic multi-card presentation with an information hierarchy based on coach workflows.

Proposed content order:

1. Page header and relevant primary action.
2. Real KPI metrics.
3. Today's sessions, when implemented and supported by data.
4. Client activity and pending coaching work.
5. Recent analyses.
6. Quick access to existing client workflows.

Currently unavailable sections should not display simulated production data.

Avoid showing multiple large empty panels.

### 11.3 Client List

Improve the current side-panel list.

Provide:

- Search
- Compact client cards or rows
- Clear selected state
- Status indicators
- Client identity information
- Responsive behavior

For future gym management, the wider membership registry should support a searchable, paginated data table.

Do not merge gym member records and personal-training clients conceptually until their domain relationship is properly designed.

### 11.4 Client Profile

Make the client profile a flagship experience.

Recommended layout:

- Compact identity header with name, avatar, status, goal.
- Horizontal tabs.
- Core metrics.
- Profile summary.
- Current goal.
- Workout plan summary.
- Nutrition plan summary.
- Progress photos.
- Latest movement analysis.
- Recent activity.

Maintain the existing routes, API responses, and functional data interactions.

Tabs:

- Overview
- Nutrition
- Workout
- Form Analysis

Additional tabs such as Progress and Notes should only be introduced when working features are available.

### 11.5 Workout Workspace

Build visual foundations for future advanced workout programming.

Use:

- Clear plan headers
- Training day sections
- Exercise lists
- Sets/reps/rest presentation
- Plan status
- History
- Dedicated create/edit actions

Preserve existing workout plan generation and editing behavior.

### 11.6 Nutrition Workspace

Create structured nutrition plan sections.

Support visual treatment for:

- Meal entries
- Nutritional targets
- Plan status
- Meal schedules
- Notes
- History

Do not introduce calculated macros unless supported by existing data.

### 11.7 Progress Photos

Replace large, poorly constrained image rendering with a consistent photo gallery.

Provide:

- Image thumbnails
- Capture dates
- Check-in labels
- Fullscreen viewing
- Consistent aspect ratios
- Placeholder states
- Privacy-aware access controls

Preserve existing upload, storage, and retrieval behavior.

### 11.8 Form Analysis

Use an athletic-technical presentation.

Provide visual areas for:

- Video upload
- Processing status
- Analysis history
- Video results
- Available measured values
- Summary and relevant observations

Use cyan sparingly to distinguish analysis-related visualizations.

Preserve the existing processing workflows.

### 11.9 Placeholder Pages

Do not invent full functional screens for unfinished features.

Apply the global layout and a consistent "Coming soon" or informative empty state.

Remove unnecessary placeholder copy that makes the application feel unfinished or repetitive.

## 12. Responsive Design

Support:

- Desktop: 1440px and larger
- Laptop: approximately 1024–1439px
- Tablet: approximately 768–1023px
- Mobile: below 768px

Behavior:

- Collapse sidebar to navigation drawer.
- Stack dashboard cards.
- Prioritize core actions.
- Avoid horizontal page overflow.
- Allow dense tables to scroll within their containers.
- Use responsive typography.
- Maintain comfortable touch targets.

Even though React Native applications are planned, the web application must remain usable on mobile browsers.

## 13. Design Tokens for Future React Native

Structure the design system to separate:

1. Primitive tokens: palette, spacing, typography, radius.
2. Semantic tokens: text-primary, action-primary, surface, border, success, danger.
3. Component-specific tokens where needed.

Prefer platform-neutral TypeScript tokens or a compatible token-generation approach.

React and React Native should share design tokens, not necessarily the same rendered UI components.

Do not introduce React Native into this redesign task unless it is already part of the repository.

## 14. Suggested Frontend Organization

Adapt to the existing project structure instead of imposing unnecessary restructuring.

Illustrative structure:

```
src/
  design-system/
    tokens/
      colors.ts
      typography.ts
      spacing.ts
      motion.ts
    components/
      buttons/
      cards/
      forms/
      navigation/
      tables/
      charts/
      feedback/
    layouts/
      AppShell.tsx
      PageContainer.tsx
      PageHeader.tsx
  features/
    dashboard/
    clients/
    workouts/
    nutrition/
    form-analysis/
  styles/
    global.css
```

Use the current project's TypeScript, CSS, routing, and component conventions where appropriate.

## 15. Implementation Sequence

### Phase A — Audit

Review the existing React codebase.

Identify:

- Current styling mechanism
- Routing
- Global layout
- Shared components
- Existing dependencies
- Accessibility issues
- Existing tests

Describe the proposed changes before performing broad refactors.

### Phase B — Foundations

Implement:

- Design tokens
- Typography
- Buttons
- Cards
- Status badges
- Form controls
- Navigation styles
- AppShell
- PageHeader

### Phase C — Reference Screens

Redesign only:

1. Existing dashboard
2. Existing client profile

These become the reference implementation for the remaining application.

### Phase D — Review

Ensure visual consistency, responsive behavior, and preservation of functionality.

Take screenshots at agreed desktop and mobile sizes where the environment supports it.

### Phase E — Expand

Apply the approved foundation to:

- Authentication
- Client list
- Nutrition
- Workout
- Progress photos
- Form analysis
- Remaining existing screens

Do not redesign all screens before the reference screens have been evaluated.

## 16. Acceptance Criteria

The redesign is successful when:

- Every redesigned screen follows the same color, spacing, and typography system.
- No key existing functionality is lost.
- Real application data is used without fabricated metrics.
- Empty states look intentional and polished.
- UI components can be reused across new gym management screens.
- Desktop and mobile layouts are usable.
- Keyboard navigation and focus states work.
- Text and controls satisfy appropriate WCAG AA contrast and accessibility expectations.
- Performance remains acceptable.
- The design feels premium, athletic, energetic, and distinctly Vectra.
- A new feature can be built using documented components and tokens without inventing a new visual style.

## 17. Documentation Requirement

Create and maintain a design-system document in the repository, for example:

`docs/design-system.md`

Document:

- Brand principles
- Color tokens
- Typography
- Spacing
- Components
- Data visualization rules
- Role-specific UX principles
- Responsive behavior
- Accessibility rules
- Component usage examples

All future screens must follow this document.

## Final Instruction to Codex

Start by auditing the existing frontend and proposing an implementation plan.

Then implement Phase B and Phase C only: the shared design foundations, dashboard, and client profile.

Do not modify backend functionality, database structures, or existing business workflows.

Preserve the application while transforming its visual identity into **Vectra Performance OS**.

The goal is not simply a prettier dashboard. The goal is a long-lived, scalable design system for a premium gym and coaching platform.