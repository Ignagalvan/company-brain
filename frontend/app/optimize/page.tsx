'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { AppShell } from '../app/components/AppShell'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ORG_ID = process.env.NEXT_PUBLIC_ORG_ID ?? '00000000-0000-0000-0000-000000000001'

type OptimizeAction = {
  id: string
  type: string
  title: string
  description: string
  impact_minutes: number
  impact_occurrences: number
  effort_estimate: 'low' | 'medium'
  reason: string
  target_type: 'gap' | 'document' | 'system'
  target_id: string | null
  target_topic: string | null
  cta_label: string
  cta_href: string
}

type OptimizePayload = {
  summary: {
    estimated_time_lost_current_minutes: number
    estimated_time_saved_if_top_actions_completed: number
    active_gaps_count: number
    unused_documents_count: number
    documents_helping_count: number
    coverage_rate_7d: number
    knowledge_health_score: number
  }
  top_actions: OptimizeAction[]
  quick_wins: OptimizeAction[]
  document_actions: OptimizeAction[]
  gap_actions: OptimizeAction[]
}

function formatMinutes(value: number): string {
  return `~${value} min`
}

function effortTone(value: 'low' | 'medium') {
  return value === 'low'
    ? 'bg-emerald-50 text-emerald-700'
    : 'bg-amber-50 text-amber-700'
}

function SummaryMetric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
      <p className="mt-1 text-[12px] leading-relaxed text-slate-500">{sub}</p>
    </div>
  )
}

function ActionCard({ action }: { action: OptimizeAction }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
          {action.target_type === 'gap' ? 'Gap' : action.target_type === 'document' ? 'Document' : 'System'}
        </span>
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${effortTone(action.effort_estimate)}`}>
          Esfuerzo {action.effort_estimate}
        </span>
      </div>
      <h3 className="mt-3 text-[16px] font-semibold text-slate-900">{action.title}</h3>
      <p className="mt-2 text-[14px] leading-relaxed text-slate-600">{action.description}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded-full bg-red-50 px-2.5 py-1 text-[12px] font-medium text-red-700">
          Impacto {formatMinutes(action.impact_minutes)}
        </span>
        {action.impact_occurrences > 0 && (
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[12px] font-medium text-slate-600">
            {action.impact_occurrences} consultas
          </span>
        )}
      </div>
      <p className="mt-3 text-[13px] leading-relaxed text-slate-500">{action.reason}</p>
      <div className="mt-4">
        <Link
          href={action.cta_href}
          className="inline-flex items-center rounded-lg border border-slate-200 px-3 py-2 text-[13px] font-medium text-slate-700 hover:bg-slate-50 transition-colors"
        >
          {action.cta_label}
        </Link>
      </div>
    </div>
  )
}

function Section({
  title,
  subtitle,
  actions,
  columns = 'grid-cols-1 xl:grid-cols-2',
}: {
  title: string
  subtitle: string
  actions: OptimizeAction[]
  columns?: string
}) {
  if (actions.length === 0) return null
  return (
    <section className="mb-6">
      <div className="mb-3">
        <h2 className="text-[18px] font-semibold text-slate-900">{title}</h2>
        <p className="mt-1 text-[14px] text-slate-500">{subtitle}</p>
      </div>
      <div className={`grid gap-4 ${columns}`}>
        {actions.map(action => (
          <ActionCard key={action.id} action={action} />
        ))}
      </div>
    </section>
  )
}

export default function OptimizePage() {
  const [data, setData] = useState<OptimizePayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetch(`${API_URL}/internal/optimize`, {
      headers: { 'X-Organization-Id': ORG_ID },
    })
      .then(res => (res.ok ? res.json() : Promise.reject()))
      .then((payload: OptimizePayload) => {
        setData(payload)
        setLoading(false)
      })
      .catch(() => {
        setError(true)
        setLoading(false)
      })
  }, [])

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto bg-slate-50">
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
          <section className="mb-6 rounded-3xl border border-slate-200 bg-white p-5 sm:p-6">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">Optimize</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">Qué conviene hacer ahora</h1>
            <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-slate-500">
              Esta vista concentra decisiones accionables basadas en gaps, documentos y salud del conocimiento. No muestra estado: te ayuda a decidir prioridades.
            </p>

            {data && (
              <div className="mt-5 grid gap-3 md:grid-cols-3">
                <div className="rounded-2xl bg-slate-900 px-4 py-4 text-white">
                  <p className="text-[12px] font-medium text-slate-300">Hoy estás perdiendo</p>
                  <p className="mt-2 text-3xl font-semibold">{formatMinutes(data.summary.estimated_time_lost_current_minutes)}</p>
                  <p className="mt-2 text-[13px] leading-relaxed text-slate-300">por gaps activos que todavía siguen afectando consultas reales.</p>
                </div>
                <div className="rounded-2xl bg-emerald-50 px-4 py-4">
                  <p className="text-[12px] font-medium text-emerald-700">Top 3 acciones</p>
                  <p className="mt-2 text-3xl font-semibold text-emerald-900">{formatMinutes(data.summary.estimated_time_saved_if_top_actions_completed)}</p>
                  <p className="mt-2 text-[13px] leading-relaxed text-emerald-800">podrían recuperarse si resolvés primero las acciones con mayor retorno.</p>
                </div>
                <div className="rounded-2xl bg-amber-50 px-4 py-4">
                  <p className="text-[12px] font-medium text-amber-700">Knowledge health</p>
                  <p className="mt-2 text-3xl font-semibold text-amber-900">{data.summary.knowledge_health_score}/100</p>
                  <p className="mt-2 text-[13px] leading-relaxed text-amber-800">con {Math.round(data.summary.coverage_rate_7d * 100)}% de cobertura en los últimos 7 días.</p>
                </div>
              </div>
            )}
          </section>

          {loading && (
            <div className="space-y-3">
              {[0, 1, 2].map(i => (
                <div key={i} className="h-28 animate-pulse rounded-2xl border border-slate-200 bg-white" />
              ))}
            </div>
          )}

          {error && !loading && (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700">
              No se pudo cargar Optimize desde el backend.
            </div>
          )}

          {data && !loading && !error && (
            <>
              <section className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <SummaryMetric
                  label="Gaps activos"
                  value={String(data.summary.active_gaps_count)}
                  sub="Problemas abiertos que hoy siguen afectando consultas."
                />
                <SummaryMetric
                  label="Docs sin uso"
                  value={String(data.summary.unused_documents_count)}
                  sub="Contenido que todavía no muestra valor visible."
                />
                <SummaryMetric
                  label="Docs útiles"
                  value={String(data.summary.documents_helping_count)}
                  sub="Documentos que sí aparecen en respuestas."
                />
                <SummaryMetric
                  label="Cobertura 7d"
                  value={`${Math.round(data.summary.coverage_rate_7d * 100)}%`}
                  sub="Nivel reciente de cobertura del conocimiento."
                />
              </section>

              <Section
                title="Qué conviene hacer ahora"
                subtitle="Las acciones con mayor retorno esperado según el sistema actual."
                actions={data.top_actions}
              />

              <Section
                title="Quick wins"
                subtitle="Acciones de bajo esfuerzo y retorno visible."
                actions={data.quick_wins}
                columns="grid-cols-1 md:grid-cols-3"
              />

              <Section
                title="Documents to review"
                subtitle="Documentos que conviene revisar, mejorar o limpiar."
                actions={data.document_actions}
              />

              <Section
                title="Gaps to resolve"
                subtitle="Los gaps más relevantes para atacar ahora."
                actions={data.gap_actions}
              />
            </>
          )}
        </main>
      </div>
    </AppShell>
  )
}
