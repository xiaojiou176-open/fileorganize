import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/lib/i18n'

const pieColors = ['hsl(var(--brand))', 'hsl(var(--accent-strong))', 'hsl(var(--success))', 'hsl(var(--warning))', 'hsl(var(--primary))']

interface ChartDatum {
  name: string
  value: number
}

interface ReportChartsGridProps {
  categoryData: ChartDatum[]
  errorCodeData: ChartDatum[]
  mediaTypeData: ChartDatum[]
  statusData: ChartDatum[]
  activeFilters: {
    category: string
    error: string
    media: string
    status: string
  }
  onSelectFilter: (key: 'category' | 'media' | 'error' | 'status', value: string) => void
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function getChartKey(payload: unknown): string {
  if (!isRecord(payload)) {
    return ''
  }
  if (typeof payload.name === 'string') {
    return payload.name
  }
  if (isRecord(payload.payload) && typeof payload.payload.name === 'string') {
    return payload.payload.name
  }
  return ''
}

function ChartCard({
  title,
  data,
  type,
  activeKey,
  onSelect,
}: {
  title: string
  data: ChartDatum[]
  type: 'pie' | 'bar'
  activeKey: string
  onSelect: (key: string) => void
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-56 w-full">
          <ResponsiveContainer>
            {type === 'pie' ? (
              <PieChart>
                <Pie
                  data={data}
                  dataKey="value"
                  innerRadius={50}
                  outerRadius={88}
                  paddingAngle={3}
                  onClick={(entry) => {
                    const key = getChartKey(entry)
                    onSelect(key)
                  }}
                >
                  {data.map((item, index) => (
                    <Cell
                      fill={item.name === activeKey ? 'hsl(var(--destructive))' : pieColors[index % pieColors.length]}
                      key={item.name}
                      style={{ cursor: 'pointer' }}
                    />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            ) : (
              <BarChart data={data} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis axisLine={false} dataKey="name" fontSize={11} tickLine={false} />
                <YAxis allowDecimals={false} axisLine={false} fontSize={11} tickLine={false} />
                <Tooltip />
                <Bar
                  dataKey="value"
                  onClick={(entry) => {
                    const key = getChartKey(entry)
                    onSelect(key)
                  }}
                  radius={[8, 8, 0, 0]}
                >
                  {data.map((item) => (
                    <Cell
                      fill={item.name === activeKey ? 'hsl(var(--destructive))' : 'hsl(var(--brand))'}
                      key={item.name}
                      style={{ cursor: 'pointer' }}
                    />
                  ))}
                </Bar>
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {data.map((item) => {
            const active = item.name === activeKey
            return (
              <Button
                aria-pressed={active}
                className={
                  active
                    ? 'rounded-full border border-destructive bg-destructive/10 px-2.5 py-1 text-xs font-medium text-destructive'
                    : 'rounded-full border border-border bg-background px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted'
                }
                key={`${title}-${item.name}`}
                onClick={() => onSelect(item.name)}
                size="sm"
                type="button"
                variant="ghost"
              >
                {item.name} · {item.value}
              </Button>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

export function ReportChartsGrid({ categoryData, errorCodeData, mediaTypeData, statusData, activeFilters, onSelectFilter }: ReportChartsGridProps) {
  const { t } = useI18n()
  return (
    <>
      <ChartCard activeKey={activeFilters.category} data={categoryData} onSelect={(key) => onSelectFilter('category', key)} title={t('report.charts.categoryDistribution')} type="pie" />
      <ChartCard activeKey={activeFilters.media} data={mediaTypeData} onSelect={(key) => onSelectFilter('media', key)} title={t('report.charts.mediaTypeDistribution')} type="bar" />
      <ChartCard activeKey={activeFilters.error} data={errorCodeData} onSelect={(key) => onSelectFilter('error', key)} title={t('report.charts.errorCodeDistribution')} type="bar" />
      <ChartCard activeKey={activeFilters.status} data={statusData} onSelect={(key) => onSelectFilter('status', key)} title={t('report.charts.statusDistribution')} type="pie" />
    </>
  )
}
