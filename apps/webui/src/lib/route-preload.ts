type DashboardModule = typeof import('@/pages/dashboard-page')
type JobsModule = typeof import('@/pages/jobs-page')
type AnalyzeModule = typeof import('@/pages/analyze-page')
type ManifestModule = typeof import('@/pages/manifest-page')
type ConflictModule = typeof import('@/pages/conflict-page')
type ApplyModule = typeof import('@/pages/apply-page')
type ReportModule = typeof import('@/pages/report-page')
type RollbackModule = typeof import('@/pages/rollback-page')
type NotFoundModule = typeof import('@/pages/not-found-page')

export const routeModules = {
  dashboard: () => import('@/pages/dashboard-page') as Promise<DashboardModule>,
  jobs: () => import('@/pages/jobs-page') as Promise<JobsModule>,
  analyze: () => import('@/pages/analyze-page') as Promise<AnalyzeModule>,
  manifest: () => import('@/pages/manifest-page') as Promise<ManifestModule>,
  conflicts: () => import('@/pages/conflict-page') as Promise<ConflictModule>,
  apply: () => import('@/pages/apply-page') as Promise<ApplyModule>,
  report: () => import('@/pages/report-page') as Promise<ReportModule>,
  rollback: () => import('@/pages/rollback-page') as Promise<RollbackModule>,
  notFound: () => import('@/pages/not-found-page') as Promise<NotFoundModule>,
}

export function preloadRouteByPath(path: string) {
  if (path === '/') {
    return routeModules.dashboard()
  }
  if (path.startsWith('/jobs')) {
    return routeModules.jobs()
  }
  if (path.startsWith('/analyze')) {
    return routeModules.analyze()
  }
  if (path.startsWith('/manifest')) {
    return routeModules.manifest()
  }
  if (path.startsWith('/conflicts')) {
    return routeModules.conflicts()
  }
  if (path.startsWith('/apply')) {
    return routeModules.apply()
  }
  if (path.startsWith('/report')) {
    return routeModules.report()
  }
  if (path.startsWith('/rollback')) {
    return routeModules.rollback()
  }
  return routeModules.notFound()
}
