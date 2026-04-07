import { Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/components/layout/app-shell'
import { PageSkeleton } from '@/components/ui/skeleton'
import { I18nProvider, useI18n } from '@/lib/i18n'
import {
  AnalyzePage,
  ApplyPage,
  ConflictPage,
  DashboardPage,
  InboxPage,
  JobsPage,
  ManifestPage,
  NotFoundPage,
  ReviewQueuePage,
  ReportPage,
  RollbackPage,
  SetupPage,
} from '@/routes/lazy-routes'

function RouteFallback() {
  const { t } = useI18n()
  return (
    <section aria-busy="true" aria-live="polite" className="motion-surface rounded-2xl border border-border/80 bg-card/85 p-4 shadow-card">
      <p className="mb-3 text-sm text-muted-foreground">{t('app.routeFallback.preloadingNextScreen')}</p>
      <PageSkeleton />
    </section>
  )
}

function withRouteSuspense(element: ReactNode) {
  return <Suspense fallback={<RouteFallback />}>{element}</Suspense>
}

function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />} path="/">
        <Route element={withRouteSuspense(<DashboardPage />)} index />
        <Route element={withRouteSuspense(<SetupPage />)} path="setup" />
        <Route element={withRouteSuspense(<JobsPage />)} path="jobs" />
        <Route element={withRouteSuspense(<AnalyzePage />)} path="analyze" />
        <Route element={withRouteSuspense(<ReviewQueuePage />)} path="review/:jobId" />
        <Route element={withRouteSuspense(<ManifestPage />)} path="manifest/:jobId" />
        <Route element={withRouteSuspense(<ConflictPage />)} path="conflicts/:jobId" />
        <Route element={withRouteSuspense(<ApplyPage />)} path="apply/:jobId" />
        <Route element={withRouteSuspense(<ReportPage />)} path="report/:jobId" />
        <Route element={withRouteSuspense(<RollbackPage />)} path="rollback/:jobId" />
        <Route element={withRouteSuspense(<InboxPage />)} path="inbox" />
      </Route>
      <Route element={<Navigate replace to="/" />} path="" />
      <Route element={withRouteSuspense(<NotFoundPage />)} path="*" />
    </Routes>
  )
}

export default function App() {
  return (
    <I18nProvider>
      <AppRoutes />
    </I18nProvider>
  )
}
