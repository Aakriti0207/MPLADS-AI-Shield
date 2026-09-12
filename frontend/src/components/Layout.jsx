// Phase 2: the sidebar/topbar/routing shell was split into reusable
// components/layout/{AppShell,Sidebar,Topbar,PageContainer,Breadcrumbs}.
// This file is kept (re-exporting AppShell) so existing imports of
// './Layout' -- including the Phase 1 logout test -- keep working.
export { default } from './layout/AppShell'
