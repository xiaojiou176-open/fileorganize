import { lazy, type ComponentType, type LazyExoticComponent } from 'react'

export type RoutePreloadKey = 'dashboard' | 'setup' | 'jobs' | 'analyze' | 'review' | 'manifest' | 'conflicts' | 'apply' | 'report' | 'rollback' | 'inbox' | 'notFound'

type RouteModule = Record<string, unknown>
type PrefetchHandlers = {
  onFocus: () => void
  onMouseEnter: () => void
  onMouseLeave: () => void
  onPointerDown: () => void
  onBlur: () => void
  onTouchStart: () => void
}
type NetworkConnection = {
  saveData?: boolean
  effectiveType?: string
}

const routeImporters: Record<RoutePreloadKey, () => Promise<RouteModule>> = {
  dashboard: () => import('@/pages/dashboard-page'),
  setup: () => import('@/pages/setup-page'),
  jobs: () => import('@/pages/jobs-page'),
  analyze: () => import('@/pages/analyze-page'),
  review: () => import('@/pages/review-queue-page'),
  manifest: () => import('@/pages/manifest-page'),
  conflicts: () => import('@/pages/conflict-page'),
  apply: () => import('@/pages/apply-page'),
  report: () => import('@/pages/report-page'),
  rollback: () => import('@/pages/rollback-page'),
  inbox: () => import('@/pages/inbox-page'),
  notFound: () => import('@/pages/not-found-page'),
}

const routeExportNames: Record<RoutePreloadKey, string> = {
  dashboard: 'DashboardPage',
  setup: 'SetupPage',
  jobs: 'JobsPage',
  analyze: 'AnalyzePage',
  review: 'ReviewQueuePage',
  manifest: 'ManifestPage',
  conflicts: 'ConflictPage',
  apply: 'ApplyPage',
  report: 'ReportPage',
  rollback: 'RollbackPage',
  inbox: 'InboxPage',
  notFound: 'NotFoundPage',
}

const preloadCache = new Map<RoutePreloadKey, Promise<RouteModule>>()
const LIKELY_NEXT_DELAY_MS = 40
const IDLE_WARMUP_TIMEOUT_MS = 1300
const IDLE_WARMUP_FALLBACK_DELAY_MS = 240
const IDLE_WARMUP_BUDGET = 2
const LOW_BANDWIDTH_WARMUP_BUDGET = 1
const INTENT_PREFETCH_DELAY_MS = 80
const IS_TEST_ENV = import.meta.env.MODE === 'test'

function uniqueKeys(keys: RoutePreloadKey[]): RoutePreloadKey[] {
  return [...new Set(keys)]
}

function preloadMany(keys: RoutePreloadKey[]) {
  for (const key of uniqueKeys(keys)) {
    void preloadRoute(key)
  }
}

function preloadManyFresh(keys: RoutePreloadKey[], budget: number) {
  if (budget <= 0) {
    return
  }
  let started = 0
  for (const key of uniqueKeys(keys)) {
    if (preloadCache.has(key)) {
      continue
    }
    void preloadRoute(key)
    started += 1
    if (started >= budget) {
      return
    }
  }
}

function getLikelyNextRouteKeys(pathname: string): RoutePreloadKey[] {
  if (pathname === '/') {
    return ['setup', 'analyze', 'jobs']
  }
  if (pathname.startsWith('/setup')) {
    return ['analyze', 'dashboard', 'jobs']
  }
  if (pathname.startsWith('/jobs')) {
    return ['manifest', 'report', 'analyze']
  }
  if (pathname.startsWith('/analyze')) {
    return ['review', 'manifest', 'apply']
  }
  if (pathname.startsWith('/review')) {
    return ['manifest', 'conflicts', 'apply']
  }
  if (pathname.startsWith('/manifest')) {
    return ['conflicts', 'apply', 'report']
  }
  if (pathname.startsWith('/conflicts')) {
    return ['manifest', 'apply']
  }
  if (pathname.startsWith('/apply')) {
    return ['report', 'rollback']
  }
  if (pathname.startsWith('/report')) {
    return ['rollback', 'jobs']
  }
  if (pathname.startsWith('/rollback')) {
    return ['jobs', 'report']
  }
  if (pathname.startsWith('/inbox')) {
    return ['review', 'jobs', 'analyze']
  }
  return []
}

function getIdleWarmupRouteKeys(pathname: string): RoutePreloadKey[] {
  if (pathname === '/') {
    return ['setup', 'report', 'apply']
  }
  if (pathname.startsWith('/setup')) {
    return ['manifest', 'apply', 'report']
  }
  if (pathname.startsWith('/jobs')) {
    return ['apply', 'report', 'rollback']
  }
  if (pathname.startsWith('/analyze')) {
    return ['review', 'conflicts', 'jobs']
  }
  if (pathname.startsWith('/review')) {
    return ['manifest', 'apply', 'report']
  }
  if (pathname.startsWith('/manifest') || pathname.startsWith('/conflicts')) {
    return ['jobs', 'report', 'rollback']
  }
  if (pathname.startsWith('/apply')) {
    return ['jobs', 'manifest', 'conflicts']
  }
  if (pathname.startsWith('/report')) {
    return ['manifest', 'apply', 'dashboard']
  }
  if (pathname.startsWith('/rollback')) {
    return ['manifest', 'apply', 'dashboard']
  }
  if (pathname.startsWith('/inbox')) {
    return ['analyze', 'review', 'jobs']
  }
  return ['dashboard', 'jobs', 'analyze']
}

function readConnection(): NetworkConnection | null {
  if (typeof navigator === 'undefined') {
    return null
  }
  const nav = navigator as Navigator & { connection?: NetworkConnection }
  return nav.connection ?? null
}

function shouldSkipWarmupPrefetch(): boolean {
  const connection = readConnection()
  if (!connection) {
    return false
  }
  const effectiveType = connection.effectiveType?.toLowerCase().trim() ?? ''
  return Boolean(connection.saveData) || effectiveType === 'slow-2g' || effectiveType === '2g'
}

function getWarmupBudget(): number {
  if (shouldSkipWarmupPrefetch()) {
    return 0
  }
  const connection = readConnection()
  const effectiveType = connection?.effectiveType?.toLowerCase().trim() ?? ''
  if (effectiveType === '3g') {
    return LOW_BANDWIDTH_WARMUP_BUDGET
  }
  return IDLE_WARMUP_BUDGET
}

function lazyRoute(key: RoutePreloadKey): LazyExoticComponent<ComponentType> {
  return lazy(async () => {
    const routeModule = await preloadRoute(key)
    const componentName = routeExportNames[key]
    const component = routeModule[componentName]
    if (!component) {
      throw new Error(`Route export "${componentName}" not found for key "${key}"`)
    }
    return { default: component as ComponentType }
  })
}

export function preloadRoute(key: RoutePreloadKey): Promise<RouteModule> {
  const cached = preloadCache.get(key)
  if (cached) {
    return cached
  }
  const promise = routeImporters[key]()
  preloadCache.set(key, promise)
  return promise
}

export function preloadRouteSet(...keys: RoutePreloadKey[]) {
  if (IS_TEST_ENV) {
    return
  }
  preloadMany(keys)
}

export function createRouteIntentPrefetchHandlers(...keys: RoutePreloadKey[]): PrefetchHandlers {
  if (IS_TEST_ENV) {
    return {
      onMouseEnter: () => undefined,
      onFocus: () => undefined,
      onPointerDown: () => undefined,
      onTouchStart: () => undefined,
      onMouseLeave: () => undefined,
      onBlur: () => undefined,
    }
  }

  let timerId = 0

  const schedule = () => {
    window.clearTimeout(timerId)
    timerId = window.setTimeout(() => {
      preloadMany(keys)
      timerId = 0
    }, INTENT_PREFETCH_DELAY_MS)
  }

  const cancel = () => {
    window.clearTimeout(timerId)
    timerId = 0
  }

  return {
    onMouseEnter: () => schedule(),
    onFocus: () => preloadMany(keys),
    onPointerDown: () => preloadMany(keys),
    onTouchStart: () => preloadMany(keys),
    onMouseLeave: () => cancel(),
    onBlur: () => cancel(),
  }
}

export function preloadLikelyNextRoutes(pathname: string) {
  if (IS_TEST_ENV) {
    return
  }
  preloadMany(getLikelyNextRouteKeys(pathname))
}

export function scheduleLikelyRoutePreload(pathname: string): () => void {
  if (IS_TEST_ENV) {
    return () => undefined
  }

  const likelyKeys = getLikelyNextRouteKeys(pathname)
  const warmupKeys = getIdleWarmupRouteKeys(pathname).filter((key) => !likelyKeys.includes(key))
  const warmupBudget = getWarmupBudget()

  if (typeof window === 'undefined') {
    preloadMany(likelyKeys)
    preloadManyFresh(warmupKeys, warmupBudget)
    return () => undefined
  }

  const idleWindow = window as Window & {
    cancelIdleCallback?: (id: number) => void
    requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number
  }
  const likelyTimer = window.setTimeout(() => {
    preloadMany(likelyKeys)
  }, LIKELY_NEXT_DELAY_MS)
  if (warmupBudget <= 0) {
    return () => {
      window.clearTimeout(likelyTimer)
    }
  }

  if (typeof idleWindow.requestIdleCallback === 'function') {
    const idleId = idleWindow.requestIdleCallback(
      () => {
        preloadManyFresh(warmupKeys, warmupBudget)
      },
      { timeout: IDLE_WARMUP_TIMEOUT_MS },
    )
    return () => {
      window.clearTimeout(likelyTimer)
      idleWindow.cancelIdleCallback?.(idleId)
    }
  }

  const timer = window.setTimeout(() => {
    preloadManyFresh(warmupKeys, warmupBudget)
  }, IDLE_WARMUP_FALLBACK_DELAY_MS)
  return () => {
    window.clearTimeout(likelyTimer)
    window.clearTimeout(timer)
  }
}

export const DashboardPage = lazyRoute('dashboard')
export const SetupPage = lazyRoute('setup')
export const JobsPage = lazyRoute('jobs')
export const AnalyzePage = lazyRoute('analyze')
export const ReviewQueuePage = lazyRoute('review')
export const ManifestPage = lazyRoute('manifest')
export const ConflictPage = lazyRoute('conflicts')
export const ApplyPage = lazyRoute('apply')
export const ReportPage = lazyRoute('report')
export const RollbackPage = lazyRoute('rollback')
export const InboxPage = lazyRoute('inbox')
export const NotFoundPage = lazyRoute('notFound')
