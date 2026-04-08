'use client'

import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { AppShell } from '../../app/components/AppShell'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ORG_ID = process.env.NEXT_PUBLIC_ORG_ID ?? '00000000-0000-0000-0000-000000000001'
const HEADERS = {
  'Content-Type': 'application/json',
  'X-Organization-Id': ORG_ID,
}

// ─── Types ────────────────────────────────────────────────────────────────────

type Suggestion = {
  topic: string
  display_label: string
  status: 'pending' | 'conflict'
  coverage_type: 'none' | 'partial'
  priority: 'high' | 'medium' | 'low_quality'
  priority_score: number
  quality: 'valid' | 'low_quality'
  occurrences: number
  avg_coverage_score: number
  suggested_action: 'create_document' | 'improve_document'
  has_existing_draft: boolean
  ready_for_draft: boolean
  draft_content: string | null
  last_seen_at: string
  evidence_snippets?: string[]
  evidence_documents?: string[]
  evidence_document_ids?: string[]
  minutes_lost_per_occurrence: number
  estimated_time_lost_minutes: number
  estimated_time_saved_if_resolved_minutes: number
}

type Insights = {
  total_active_gaps: number
  high_priority_count: number
  coverage_rate: number
  recently_resolved: number
  total_queries_analyzed: number
  active_gaps: number
  resolved_gaps: number
  coverage_rate_7d: number
  estimated_time_lost_current_minutes: number
  estimated_time_saved_recent_minutes: number
  knowledge_health_score: number
  top_topics: Array<{
    topic: string
    display_label?: string
    coverage_type: string
    occurrences: number
    priority_score: number
    priority: string
    estimated_time_saved_if_resolved_minutes: number
  }>
}

type QuickWin = {
  topic: string
  display_label: string
  coverage_type: 'none' | 'partial'
  priority: 'high' | 'medium' | 'low_quality'
  priority_score: number
  occurrences: number
  estimated_time_saved_if_resolved_minutes: number
  summary: string
}

type Recommendation = {
  kind: string
  title: string
  topic: string
  display_label: string
  reason: string
  estimated_time_saved_if_resolved_minutes: number
  occurrences: number
  coverage_type: 'none' | 'partial'
  priority: 'high' | 'medium' | 'low_quality'
}

type Draft = {
  draft_title: string
  draft_content: string
  draft_type: string
}

type PromoteResult = {
  document_id: string
  filename: string
  chunks_created: number
  promoted_at: string
  knowledge_impact?: {
    topic: string
    coverage_before: 'none' | 'partial'
    coverage_after: 'full'
    affected_occurrences: number
    estimated_time_saved_if_resolved_minutes: number
    message: string
  } | null
}

type AppliedItem = {
  topic: string
  display_label?: string
  coverage_type: 'none' | 'partial'
  chunks_created: number
  promoted_at: string
  occurrences: number
  estimated_time_saved_if_resolved_minutes: number
}

type EvidenceSnippet = {
  text: string
  source: string
}

type ItemStatus =
  | { tag: 'idle' }
  | { tag: 'reviewing' }
  | { tag: 'ignoring' }
  | { tag: 'ignored' }
  | { tag: 'generating' }
  | { tag: 'draft_ready'; draft: Draft }
  | { tag: 'promoting'; draft: Draft }
  | { tag: 'promoted'; draft: Draft; result: PromoteResult }
  | { tag: 'conflict'; draft?: Draft }
  | { tag: 'error'; message: string }
  | { tag: 'validation_error'; reason: string }

type SortKey = 'impact' | 'frequency' | 'recent'

// ─── Topic validation ─────────────────────────────────────────────────────────

function isTopicValid(topic: string): { valid: boolean; reason?: string } {
  const trimmed = topic.trim()
  const noSpaces = trimmed.replace(/\s+/g, '').toLowerCase()
  if (noSpaces.length === 0) return { valid: false, reason: 'El topic está vacío.' }
  const charCounts: Record<string, number> = {}
  for (const c of noSpaces) charCounts[c] = (charCounts[c] ?? 0) + 1
  const maxCount = Math.max(...Object.values(charCounts))
  if (maxCount / noSpaces.length > 0.5) {
    return { valid: false, reason: 'Este topic no parece válido para generar documentación. Reformulá la consulta.' }
  }
  const longestWord = Math.max(...trimmed.split(/\s+/).map(w => w.length))
  if (longestWord > 30) {
    return { valid: false, reason: 'Este topic no parece válido para generar documentación. Reformulá la consulta.' }
  }
  if (noSpaces.length > 6 && new Set(noSpaces).size < 4) {
    return { valid: false, reason: 'Este topic no parece válido para generar documentación. Reformulá la consulta.' }
  }
  return { valid: true }
}

// ─── Relative time ────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'hace un momento'
  if (mins < 60) return `hace ${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `hace ${hrs}h`
  const days = Math.floor(hrs / 24)
  return `hace ${days}d`
}

function formatMinutes(minutes: number): string {
  return `~${minutes} min`
}

function formatCoveragePct(rate: number): string {
  return `${Math.round(rate * 100)}%`
}

function consultasLabel(count: number): string {
  return count === 1 ? 'consulta' : 'consultas'
}

function isImproveFlow(suggestion: Suggestion): boolean {
  return suggestion.suggested_action === 'improve_document' || suggestion.coverage_type === 'partial'
}

function primaryDraftLabel(suggestion: Suggestion, compact = false): string {
  if (isImproveFlow(suggestion)) return compact ? 'Completar' : 'Completar respuesta'
  return compact ? 'Propuesta' : 'Crear contenido'
}

function truncateEvidence(value: string, max = 200): string {
  const compact = value.replace(/\s+/g, ' ').trim()
  if (compact.length <= max) return compact
  return `${compact.slice(0, max).trimEnd()}...`
}

function backendEvidenceSnippets(suggestion: Suggestion): EvidenceSnippet[] {
  const snippets = suggestion.evidence_snippets ?? []
  const documents = suggestion.evidence_documents ?? []
  return snippets.slice(0, 2).map((text, index) => ({
    text: truncateEvidence(text),
    source: documents[index] ?? documents[0] ?? 'Documento',
  }))
}

function ensureSentence(value: string): string {
  const trimmed = value.replace(/\s+/g, ' ').trim()
  if (!trimmed) return ''
  return /[.!?…]$/.test(trimmed) ? trimmed : `${trimmed}.`
}

function suggestedResponseCopy(suggestion: Suggestion, evidenceSnippets: EvidenceSnippet[]): string {
  if (evidenceSnippets.length > 0) {
    return ensureSentence(evidenceSnippets[0].text)
  }

  const label = (suggestion.display_label ?? suggestion.topic).replace(/^¿/, '').replace(/\?$/, '').trim()
  return `Hay información relacionada sobre ${label.toLowerCase()}, pero no alcanza para responder completamente la pregunta.`
}

function sanitizeDraftContent(value: string): string {
  return value
    .split(/\r?\n/)
    .filter(line => {
      const normalized = line.trim().toLowerCase()
      if (!normalized) return true
      return ![
        'documentación sobre',
        'documentacion sobre',
        'descripción general',
        'descripcion general',
        'notas importantes',
      ].some(prefix => normalized.startsWith(prefix))
    })
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function documentHrefFromSuggestion(suggestion: Suggestion): string {
  const documentId = suggestion.evidence_document_ids?.[0]
  return documentId ? `/documents/${documentId}` : '/documents'
}

function healthTone(score: number): { label: string; valueClass: string; subClass: string } {
  if (score >= 80) return { label: 'Salud fuerte', valueClass: 'text-emerald-600', subClass: 'text-emerald-500' }
  if (score >= 60) return { label: 'Salud estable', valueClass: 'text-amber-600', subClass: 'text-amber-500' }
  return { label: 'Salud fragil', valueClass: 'text-red-600', subClass: 'text-red-500' }
}

// ─── Sort ─────────────────────────────────────────────────────────────────────

function sortSuggestions(items: Suggestion[], key: SortKey): Suggestion[] {
  const copy = [...items]
  if (key === 'impact') {
    return copy.sort((a, b) =>
      b.estimated_time_saved_if_resolved_minutes - a.estimated_time_saved_if_resolved_minutes
      || b.priority_score - a.priority_score
      || b.occurrences - a.occurrences
    )
  }
  if (key === 'frequency') return copy.sort((a, b) => b.occurrences - a.occurrences)
  // recent: newest last_seen_at first
  return copy.sort((a, b) => new Date(b.last_seen_at).getTime() - new Date(a.last_seen_at).getTime())
}

// ─── Badges ───────────────────────────────────────────────────────────────────

function CoverageBadge({ type }: { type: 'none' | 'partial' }) {
  if (type === 'none') {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-red-50 text-red-600 border border-red-100">
        Sin cobertura
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-600 border border-amber-100">
      Parcial
    </span>
  )
}

function PriorityDot({ priority }: { priority: string }) {
  if (priority === 'high') return <span className="w-2 h-2 rounded-full bg-red-500 shrink-0 inline-block" />
  if (priority === 'medium') return <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0 inline-block" />
  return <span className="w-2 h-2 rounded-full bg-slate-300 shrink-0 inline-block" />
}

function StatusChip({ status }: { status: 'pending' | 'conflict' }) {
  if (status === 'conflict') {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-600 border border-amber-200">
        Conflicto
      </span>
    )
  }
  return null
}

function DocumentedBadge() {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-100">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
      Documentado
    </span>
  )
}

// ─── Insights bar ─────────────────────────────────────────────────────────────

function InsightsBar({ insights }: { insights: Insights | null }) {
  if (!insights) return null
  const coveragePct = Math.round(insights.coverage_rate * 100)
  const topTopic = insights.top_topics[0]
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-6">
      <MetricCard
        label="Gaps activos"
        value={String(insights.total_active_gaps)}
        sub={insights.high_priority_count > 0 ? `${insights.high_priority_count} alta prioridad` : undefined}
        valueColor={insights.total_active_gaps > 0 ? 'text-slate-900' : 'text-slate-400'}
        subColor={insights.high_priority_count > 0 ? 'text-red-500' : undefined}
      />
      <MetricCard
        label="Alta prioridad"
        value={String(insights.high_priority_count)}
        sub={topTopic ? `"${(topTopic.display_label ?? topTopic.topic).length > 22 ? (topTopic.display_label ?? topTopic.topic).slice(0, 22) + '…' : (topTopic.display_label ?? topTopic.topic)}"` : undefined}
        valueColor={insights.high_priority_count > 0 ? 'text-red-500 font-bold' : 'text-slate-400'}
      />
      <MetricCard
        label="Cobertura (7d)"
        value={`${coveragePct}%`}
        sub={coveragePct < 60 ? 'Baja' : coveragePct < 80 ? 'Media' : 'Buena'}
        valueColor={coveragePct >= 80 ? 'text-emerald-600' : coveragePct >= 60 ? 'text-amber-500' : 'text-red-500'}
        subColor={coveragePct >= 80 ? 'text-emerald-500' : coveragePct >= 60 ? 'text-amber-400' : 'text-red-400'}
      />
      <MetricCard
        label="Resueltos (24h)"
        value={String(insights.recently_resolved)}
        sub={insights.recently_resolved > 0 ? 'Conocimiento agregado' : 'Sin actividad reciente'}
        valueColor={insights.recently_resolved > 0 ? 'text-emerald-600' : 'text-slate-400'}
      />
    </div>
  )
}

function MetricCard({
  label,
  value,
  sub,
  valueColor,
  subColor,
}: {
  label: string
  value: string
  sub?: string
  valueColor?: string
  subColor?: string
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 mb-1">{label}</p>
      <p className={`text-2xl font-bold tabular-nums leading-none ${valueColor ?? 'text-slate-900'}`}>{value}</p>
      {sub && (
        <p className={`text-[11px] mt-1.5 leading-tight ${subColor ?? 'text-slate-400'}`}>{sub}</p>
      )}
    </div>
  )
}

function BusinessInsightsBar({ insights }: { insights: Insights | null }) {
  if (!insights) return null
  const coveragePct = Math.round(insights.coverage_rate_7d * 100)
  const topTopic = insights.top_topics[0]
  const health = healthTone(insights.knowledge_health_score)
  return (
    <div className="grid grid-cols-2 xl:grid-cols-6 gap-2.5 mb-6">
      <MetricCard
        label="Consultas 7d"
        value={String(insights.total_queries_analyzed)}
        sub={topTopic ? `Top gap: ${(topTopic.display_label ?? topTopic.topic).length > 18 ? `${(topTopic.display_label ?? topTopic.topic).slice(0, 18)}...` : (topTopic.display_label ?? topTopic.topic)}` : 'Sin gaps destacados'}
        valueColor={insights.total_queries_analyzed > 0 ? 'text-slate-900' : 'text-slate-400'}
      />
      <MetricCard
        label="Gaps activos"
        value={String(insights.active_gaps)}
        sub={insights.high_priority_count > 0 ? `${insights.high_priority_count} alta prioridad` : 'Sin gaps criticos'}
        valueColor={insights.active_gaps > 0 ? 'text-slate-900' : 'text-slate-400'}
        subColor={insights.high_priority_count > 0 ? 'text-red-500' : undefined}
      />
      <MetricCard
        label="Cobertura 7d"
        value={`${coveragePct}%`}
        sub={coveragePct < 60 ? 'Cobertura baja' : coveragePct < 80 ? 'Cobertura media' : 'Cobertura buena'}
        valueColor={coveragePct >= 80 ? 'text-emerald-600' : coveragePct >= 60 ? 'text-amber-500' : 'text-red-500'}
        subColor={coveragePct >= 80 ? 'text-emerald-500' : coveragePct >= 60 ? 'text-amber-400' : 'text-red-400'}
      />
      <MetricCard
        label="Tiempo perdido hoy"
        value={formatMinutes(insights.estimated_time_lost_current_minutes)}
        sub="Costo estimado en gaps activos"
        valueColor={insights.estimated_time_lost_current_minutes > 0 ? 'text-red-600' : 'text-emerald-600'}
      />
      <MetricCard
        label="Ahorro reciente"
        value={formatMinutes(insights.estimated_time_saved_recent_minutes)}
        sub={`${insights.resolved_gaps} gaps resueltos`}
        valueColor={insights.estimated_time_saved_recent_minutes > 0 ? 'text-emerald-600' : 'text-slate-400'}
      />
      <MetricCard
        label="Knowledge Health"
        value={String(insights.knowledge_health_score)}
        sub={health.label}
        valueColor={health.valueClass}
        subColor={health.subClass}
      />
    </div>
  )
}

function GapValueStrip({ suggestion }: { suggestion: Suggestion }) {
  return (
    <div className="mt-3 grid grid-cols-3 gap-2">
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Consultas</p>
        <p className="mt-1 text-[14px] font-semibold text-slate-800">{suggestion.occurrences}</p>
      </div>
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Tiempo perdido</p>
        <p className="mt-1 text-[14px] font-semibold text-slate-800">{formatMinutes(suggestion.estimated_time_lost_minutes)}</p>
      </div>
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-600">Ahorro posible</p>
        <p className="mt-1 text-[14px] font-semibold text-emerald-700">{formatMinutes(suggestion.estimated_time_saved_if_resolved_minutes)}</p>
      </div>
    </div>
  )
}

function QuickWinsPanel({ items }: { items: QuickWin[] }) {
  if (items.length === 0) return null
  return (
    <section className="mb-5 rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 via-white to-white p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700">Quick Wins</p>
          <h2 className="text-[18px] font-semibold text-slate-900 mt-1">Que resolver primero para ahorrar tiempo</h2>
        </div>
        <span className="rounded-full border border-emerald-200 bg-white px-2.5 py-1 text-[11px] font-medium text-emerald-700">
          Top 3 por ahorro estimado
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {items.map((item, index) => (
          <div key={item.topic} className="rounded-xl border border-emerald-100 bg-white p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-600">#{index + 1} Quick win</p>
            <p className="mt-2 text-[14px] font-semibold text-slate-900 leading-snug">{item.display_label ?? item.topic}</p>
            <p className="mt-2 text-[13px] text-slate-600 leading-relaxed">{item.summary}</p>
            <div className="mt-3 flex flex-wrap gap-2 text-[12px]">
              <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-600">{item.occurrences} {consultasLabel(item.occurrences)}</span>
              <span className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-700">{formatMinutes(item.estimated_time_saved_if_resolved_minutes)}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function RecommendationsPanel({ items }: { items: Recommendation[] }) {
  if (items.length === 0) return null
  return (
    <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
      <div className="mb-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Recomendaciones</p>
        <h2 className="text-[17px] font-semibold text-slate-900 mt-1">Acciones accionables basadas en datos reales</h2>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {items.map(item => (
          <div key={`${item.kind}-${item.topic}`} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[12px] font-semibold text-slate-700">{item.title}</p>
              <span className="text-[11px] text-slate-500">{formatMinutes(item.estimated_time_saved_if_resolved_minutes)}</span>
            </div>
            <p className="mt-1 text-[13px] font-medium text-slate-900">{item.display_label ?? item.topic}</p>
            <p className="mt-1 text-[12px] leading-relaxed text-slate-500">{item.reason}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

// ─── Sort controls ────────────────────────────────────────────────────────────

function SortControls({ sort, onChange }: { sort: SortKey; onChange: (k: SortKey) => void }) {
  const opts: { key: SortKey; label: string }[] = [
    { key: 'impact', label: 'Impacto' },
    { key: 'frequency', label: 'Frecuencia' },
    { key: 'recent', label: 'Reciente' },
  ]
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[11px] text-slate-400 font-medium mr-1">Ordenar:</span>
      {opts.map(o => (
        <button
          key={o.key}
          onClick={() => onChange(o.key)}
          className={[
            'text-[12px] px-2.5 py-1 rounded-md font-medium transition-colors',
            sort === o.key
              ? 'bg-slate-900 text-white'
              : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700',
          ].join(' ')}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

// ─── Explainability text ──────────────────────────────────────────────────────

function explainGap(s: Suggestion): string {
  const parts: string[] = []
  if (s.occurrences === 1) {
    parts.push('1 consulta')
  } else {
    parts.push(`${s.occurrences} consultas`)
  }
  if (s.coverage_type === 'none') {
    parts.push('sin respuesta')
  } else {
    parts.push('respuesta parcial')
  }
  if (s.last_seen_at) {
    parts.push(relativeTime(s.last_seen_at))
  }
  return parts.join(' · ')
}

// ─── Draft editor ─────────────────────────────────────────────────────────────

function DraftEditor({
  content,
  onChange,
  disabled,
}: {
  content: string
  onChange: (v: string) => void
  disabled?: boolean
}) {
  return (
    <div className="mt-4 border border-slate-200 rounded-xl overflow-hidden bg-white shadow-sm">
      <div className="bg-slate-50 border-b border-slate-200 px-5 py-3 flex items-center justify-between">
        <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wide">Contenido que se agregaría al conocimiento</span>
        <span className="text-[11px] text-slate-400 tabular-nums">{content.length} chars</span>
      </div>
      <textarea
        value={content}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        spellCheck={false}
        className="w-full px-5 py-4 text-[14px] text-slate-700 leading-7 resize-y bg-white focus:outline-none min-h-[240px] max-h-[560px] disabled:opacity-60 disabled:cursor-not-allowed"
      />
    </div>
  )
}

function ResolutionPlan({
  suggestion,
  state,
  content,
  onChange,
}: {
  suggestion: Suggestion
  state: ItemStatus
  content: string
  onChange: (v: string) => void
}) {
  const disabled = state.tag === 'promoting' || state.tag === 'promoted'
  const impact =
    state.tag === 'promoted'
      ? state.result.knowledge_impact?.estimated_time_saved_if_resolved_minutes ?? suggestion.estimated_time_saved_if_resolved_minutes
      : suggestion.estimated_time_saved_if_resolved_minutes
  const affectedOccurrences =
    state.tag === 'promoted'
      ? state.result.knowledge_impact?.affected_occurrences ?? suggestion.occurrences
      : suggestion.occurrences

  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70 overflow-hidden">
      <div className="border-b border-slate-200 bg-white px-4 py-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Resolucion guiada</p>
        <h3 className="mt-1 text-[15px] font-semibold text-slate-900">Entendé qué falta, qué propone el sistema y qué va a pasar si lo aceptás</h3>
      </div>
      <div className="grid gap-3 p-4 md:grid-cols-3">
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Que falta hoy</p>
          <p className="mt-2 text-[13px] leading-relaxed text-slate-700">
            Este tema sigue dejando preguntas sin buena cobertura en el chat.
          </p>
          <div className="mt-3 space-y-1.5 text-[12px] text-slate-600">
            <p>{affectedOccurrences} {consultasLabel(affectedOccurrences)} afectadas</p>
            <p>{suggestion.coverage_type === 'none' ? 'Hoy no hay respuesta confiable.' : 'Hoy la respuesta sigue siendo parcial.'}</p>
            <p>{formatMinutes(impact)} recuperables si queda cubierto</p>
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Que propone el sistema</p>
          <p className="mt-2 text-[13px] leading-relaxed text-slate-700">
            Esta propuesta agrega el conocimiento faltante. Podés editarla antes de guardarla.
          </p>
          <DraftEditor content={content} onChange={onChange} disabled={disabled} />
        </div>
        <div className="rounded-lg border border-emerald-200 bg-emerald-50/70 px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">Que pasa si la aceptas</p>
          <div className="mt-2 space-y-2 text-[13px] leading-relaxed text-emerald-900">
            <p>El texto se guarda como conocimiento interno y se indexa para futuras respuestas.</p>
            <p>No es la respuesta final del chat: es la base que el sistema usará para responder con evidencia.</p>
            <p>Debería cubrir preguntas como <span className="font-medium">{suggestion.display_label ?? suggestion.topic}</span> y variantes similares.</p>
          </div>
          <div className="mt-3 rounded-lg border border-emerald-200 bg-white/80 px-3 py-2 text-[12px] text-emerald-800">
            Impacto esperado: {affectedOccurrences} {consultasLabel(affectedOccurrences)} y {formatMinutes(impact)} recuperables.
          </div>
        </div>
      </div>
    </div>
  )
}

function GapResolutionPanelLegacy({
  suggestion,
  state,
  evidenceSnippets,
}: {
  suggestion: Suggestion
  state: ItemStatus
  evidenceSnippets: EvidenceSnippet[]
}) {
  const improveFlow = isImproveFlow(suggestion)
  const impact =
    state.tag === 'promoted'
      ? state.result.knowledge_impact?.estimated_time_saved_if_resolved_minutes ?? suggestion.estimated_time_saved_if_resolved_minutes
      : suggestion.estimated_time_saved_if_resolved_minutes
  const affectedOccurrences =
    state.tag === 'promoted'
      ? state.result.knowledge_impact?.affected_occurrences ?? suggestion.occurrences
      : suggestion.occurrences

  const label = suggestion.display_label ?? suggestion.topic
  const plainLabel = label.replace(/^¿/, '').replace(/\?$/, '').trim()
  const lowerLabel = plainLabel.toLowerCase()
  let coveredQuestions = [
    `¿${plainLabel}?`,
    `¿Hay información sobre ${plainLabel.toLowerCase()}?`,
    `¿Cómo responde la empresa sobre ${plainLabel.toLowerCase()}?`,
  ]

  if (lowerLabel.includes('empresa')) {
    coveredQuestions = [
      '¿Cómo se llama la empresa?',
      '¿Cuál es el nombre de la empresa?',
      '¿Qué empresa brinda este servicio?',
    ]
  } else if (lowerLabel.includes('bono')) {
    coveredQuestions = [
      '¿Hay bono anual?',
      '¿La empresa ofrece bono?',
      '¿Existe bono de fin de año?',
    ]
  } else if (lowerLabel.includes('vacaciones')) {
    coveredQuestions = [
      '¿Cuántos días de vacaciones hay?',
      '¿Cuántos días de vacaciones tienen los empleados?',
      '¿Cuántos días me corresponden de vacaciones?',
    ]
  }

  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70 overflow-hidden">
      <div className="border-b border-slate-200 bg-white px-5 py-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Resolución guiada</p>
        <h3 className="mt-1 text-[16px] font-semibold text-slate-900">Entendé el problema, revisá la propuesta y decidí si querés agregar este conocimiento</h3>
        <div className="mt-2 inline-flex rounded-full border px-2.5 py-1 text-[11px] font-medium leading-none">
          {improveFlow ? (
            <span className="border-amber-200 bg-amber-50 text-amber-700 rounded-full px-2.5 py-1 -m-1">Hay evidencia parcial: conviene mejorar contenido existente</span>
          ) : (
            <span className="border-red-200 bg-red-50 text-red-700 rounded-full px-2.5 py-1 -m-1">No hay evidencia relevante: conviene crear contenido nuevo</span>
          )}
        </div>
      </div>
      <div className="grid gap-3 p-4 md:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Qué falta hoy</p>
          <p className="mt-2 text-[13px] leading-relaxed text-slate-700">
            {improveFlow
              ? 'Hay información relacionada, pero hoy no alcanza para responder con confianza.'
              : 'Este tema sigue dejando preguntas sin buena cobertura en el chat.'}
          </p>
          <div className="mt-3 space-y-1.5 text-[12px] text-slate-600">
            <p>{affectedOccurrences} {consultasLabel(affectedOccurrences)} afectadas</p>
            <p>{suggestion.coverage_type === 'none' ? 'Hoy no hay respuesta confiable.' : 'Hoy la respuesta sigue siendo parcial.'}</p>
            <p>{formatMinutes(impact)} recuperables si queda cubierto</p>
          </div>
        </div>
        <div className="rounded-lg border border-emerald-200 bg-emerald-50/70 px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">Qué pasa si aceptás</p>
          <div className="mt-2 space-y-2 text-[13px] leading-relaxed text-emerald-900">
            <p>{improveFlow ? 'La mejora se agrega al conocimiento para reforzar lo que ya existe.' : 'El texto se guarda como conocimiento interno y se indexa para futuras respuestas.'}</p>
            <p>{improveFlow ? 'No crea una respuesta final por sí sola: mejora la base que el sistema usará para responder con evidencia.' : 'No es la respuesta final del chat: es la base que el sistema usará para responder con evidencia.'}</p>
            <p>Esto permitiría responder preguntas como:</p>
            <ul className="space-y-1 pl-4 list-disc text-[12px] text-emerald-900">
              {coveredQuestions.slice(0, 3).map(question => (
                <li key={question}>{question}</li>
              ))}
            </ul>
          </div>
          <div className="mt-3 rounded-lg border border-emerald-200 bg-white/80 px-3 py-2 text-[12px] text-emerald-800">
            Impacto esperado: {affectedOccurrences} {consultasLabel(affectedOccurrences)} y {formatMinutes(impact)} recuperables.
          </div>
        </div>
      </div>
      {improveFlow && (
        <div className="px-4 pb-4">
          <div className="rounded-lg border border-slate-200 bg-slate-100/80 px-4 py-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Ya hay información relacionada</p>
            {evidenceSnippets.length > 0 ? (
              <div className="mt-3 space-y-3">
                {evidenceSnippets.slice(0, 2).map((snippet, index) => (
                  <div key={`${snippet.source}-${index}`} className="rounded-lg border border-slate-200 bg-white px-4 py-3">
                    <p className="text-[14px] leading-7 text-slate-700">&ldquo;{snippet.text}&rdquo;</p>
                    <p className="mt-3 text-[12px] font-medium text-slate-500">Fuente: {snippet.source}</p>
                  </div>
                ))}
                <p className="text-[13px] leading-relaxed text-slate-500">
                  Esta información no alcanza para responder completamente la pregunta. Podés mejorarla para que el sistema responda correctamente.
                </p>
              </div>
            ) : (
              <div className="mt-3 rounded-lg border border-slate-200 bg-white px-4 py-3">
                <p className="text-[14px] leading-7 text-slate-700">
                  Se encontró contenido relacionado en tus documentos, pero no alcanza para responder completamente la pregunta.
                </p>
                <p className="mt-3 text-[13px] leading-relaxed text-slate-500">
                  Esta información está incompleta para responder la pregunta. Podés mejorarla para que el sistema responda correctamente.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
      <div className="px-4 pb-4">
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Qué propone el sistema</p>
          <h4 className="mt-1 text-[15px] font-semibold text-slate-900">
            {improveFlow ? 'Respuesta sugerida' : 'No hay información disponible'}
          </h4>
          {improveFlow ? (
            <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-5 py-5">
              <p className="text-[16px] leading-8 text-slate-800">
                {suggestedResponseCopy(suggestion, evidenceSnippets)}
              </p>
              <p className="mt-3 text-[13px] leading-relaxed text-slate-500">
                Esta respuesta muestra lo que ya se puede sostener con evidencia, pero todavía necesita contexto o precisión para quedar completa.
              </p>
            </div>
          ) : (
            <div className="mt-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-5">
              <p className="text-[15px] leading-7 text-slate-800">
                No hay información en los documentos para responder esta pregunta.
              </p>
              <p className="mt-3 text-[13px] leading-relaxed text-slate-600">
                Se recomienda agregar un documento o contenido que cubra este tema.
              </p>
              <div className="mt-4">
                <p className="text-[12px] font-semibold uppercase tracking-wide text-slate-400">Ejemplos de qué debería incluir</p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] text-slate-600">
                  <li>definición</li>
                  <li>condiciones</li>
                  <li>reglas</li>
                  <li>responsables</li>
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── FadingWrapper ────────────────────────────────────────────────────────────

function buildMissingBullets(suggestion: Suggestion, evidenceSnippets: EvidenceSnippet[]): string[] {
  const label = (suggestion.display_label ?? suggestion.topic).toLowerCase()
  const snippetText = evidenceSnippets.map(item => item.text.toLowerCase()).join(' ')
  const bullets: string[] = []

  if (label.includes('cuanto') || label.includes('cuánt') || label.includes('dias') || label.includes('días')) {
    bullets.push('No se especifica la cantidad o frecuencia.')
  }
  if (label.includes('condiciones') || snippetText.includes('permitid') || snippetText.includes('aprob')) {
    bullets.push('Falta detalle sobre condiciones, límites o excepciones.')
  }
  if (label.includes('como') || label.includes('cómo') || label.includes('cual') || label.includes('cuál')) {
    bullets.push('Falta una respuesta directa y completa para la pregunta.')
  }
  if (bullets.length === 0) {
    bullets.push('Falta contexto para responder la pregunta completa.')
  }
  if (bullets.length === 1) {
    bullets.push('Se necesita una versión más clara para que el sistema responda con confianza.')
  }

  return bullets.slice(0, 2)
}

function GapResolutionPanel({
  suggestion,
  state,
  evidenceSnippets,
}: {
  suggestion: Suggestion
  state: ItemStatus
  evidenceSnippets: EvidenceSnippet[]
}) {
  const improveFlow = isImproveFlow(suggestion)
  const impact =
    state.tag === 'promoted'
      ? state.result.knowledge_impact?.estimated_time_saved_if_resolved_minutes ?? suggestion.estimated_time_saved_if_resolved_minutes
      : suggestion.estimated_time_saved_if_resolved_minutes
  const affectedOccurrences =
    state.tag === 'promoted'
      ? state.result.knowledge_impact?.affected_occurrences ?? suggestion.occurrences
      : suggestion.occurrences
  const label = suggestion.display_label ?? suggestion.topic
  const plainLabel = label.replace(/^¿/, '').replace(/\?$/, '').trim()
  const lowerLabel = plainLabel.toLowerCase()
  const missingBullets = buildMissingBullets(suggestion, evidenceSnippets)
  const ctaHref = improveFlow ? documentHrefFromSuggestion(suggestion) : '/documents'
  const ctaLabel = improveFlow ? 'Ir al documento' : 'Ir a documentos'

  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70 overflow-hidden">
      <div className="border-b border-slate-200 bg-white px-5 py-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Resolución guiada</p>
        <h3 className="mt-1 text-[16px] font-semibold text-slate-900">Entendé qué encontró el sistema, qué falta y qué acción tomar</h3>
      </div>

      {improveFlow ? (
        <>
          <div className="grid gap-3 p-4 md:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-white px-4 py-4">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Qué encontró el sistema</p>
              {evidenceSnippets.length > 0 ? (
                <div className="mt-3 space-y-3">
                  {evidenceSnippets.slice(0, 2).map((snippet, index) => (
                    <div key={`${snippet.source}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                      <p className="text-[14px] leading-7 text-slate-700">&ldquo;{snippet.text}&rdquo;</p>
                      <p className="mt-2 text-[12px] font-medium text-slate-500">Fuente: {snippet.source}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-[14px] leading-7 text-slate-700">
                  Se encontró contenido relacionado en tus documentos, pero no alcanza para responder completamente la pregunta.
                </p>
              )}
            </div>

            <div className="rounded-lg border border-slate-200 bg-white px-4 py-4">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Qué falta</p>
              <ul className="mt-3 list-disc space-y-2 pl-5 text-[14px] leading-6 text-slate-700">
                {missingBullets.map(bullet => (
                  <li key={bullet}>{bullet}</li>
                ))}
              </ul>
              <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] text-slate-600">
                {affectedOccurrences} {consultasLabel(affectedOccurrences)} afectadas y {formatMinutes(impact)} recuperables si queda cubierto.
              </div>
            </div>
          </div>

          <div className="px-4 pb-4">
            <div className="rounded-lg border border-slate-200 bg-white px-4 py-4">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Acción recomendada</p>
              <p className="mt-2 text-[14px] leading-7 text-slate-700">
                Podés revisar el documento existente para completar este tema y mejorar la respuesta del sistema.
              </p>
              <div className="mt-4">
                <a
                  href={ctaHref}
                  className="inline-flex text-[13px] px-3 py-1.5 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300 font-medium transition-colors"
                >
                  {ctaLabel}
                </a>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="px-4 py-4">
          <div className="rounded-lg border border-slate-200 bg-white px-4 py-4">
            <p className="text-[15px] font-semibold text-slate-900">No hay información disponible</p>
            <p className="mt-2 text-[14px] leading-7 text-slate-700">
              No hay información en los documentos para responder esta pregunta.
            </p>
            <p className="mt-3 text-[13px] leading-relaxed text-slate-600">
              Se recomienda agregar un PDF sobre este tema.
            </p>
            <div className="mt-4">
              <a
                href={ctaHref}
                className="inline-flex text-[13px] px-3 py-1.5 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300 font-medium transition-colors"
              >
                {ctaLabel}
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function FadingWrapper({ children, fading }: { children: React.ReactNode; fading: boolean }) {
  return (
    <div
      style={{
        transition: 'opacity 300ms ease, transform 300ms ease',
        opacity: fading ? 0 : 1,
        transform: fading ? 'translateY(-4px)' : 'translateY(0)',
        pointerEvents: fading ? 'none' : undefined,
      }}
    >
      {children}
    </div>
  )
}

// ─── High-priority card ───────────────────────────────────────────────────────

function HighPriorityCard({
  suggestion,
  state,
  editedContent,
  evidenceSnippets,
  focused = false,
  onGenerateDraft,
  onPromote,
  onIgnore,
  onUndo,
  onEditContent,
}: SuggestionItemProps) {
  const s = suggestion

  if (state.tag === 'ignoring' || state.tag === 'ignored') {
    return (
      <div
        className={[
          'border-l-4 rounded-r-xl border shadow-sm transition-all duration-300 ease-out',
          state.tag === 'ignoring'
            ? 'border-l-red-300 border-red-200 bg-red-50/70 scale-[0.99]'
            : 'border-l-red-200 border-red-100 bg-red-50/60',
        ].join(' ')}
      >
        <div className="px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-semibold text-slate-900 leading-snug break-words">{s.display_label ?? s.topic}</p>
              <p className="mt-1.5 text-[13px] text-red-600">
                {state.tag === 'ignoring'
                  ? 'Ignorando gap...'
                  : 'Gap ignorado. Esta accion oculta este tema de la lista.'}
              </p>
            </div>
            {state.tag === 'ignored' && (
              <button
                onClick={onUndo}
                className="shrink-0 text-[12px] px-2.5 py-1.5 rounded-md border border-red-200 text-red-600 hover:bg-red-50 transition-colors"
              >
                Deshacer acción
              </button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      className={[
        'border-l-4 rounded-r-xl bg-white border border-l-4 shadow-sm transition-all duration-300 ease-out',
        state.tag === 'promoted'
          ? 'border-l-emerald-400 border-emerald-200 bg-emerald-50/40'
          : state.tag === 'conflict'
          ? 'border-l-amber-400 border-amber-200 bg-amber-50/30'
          : focused
          ? 'border-l-emerald-500 border-emerald-300 bg-emerald-50/40'
          : 'border-l-red-400 border-slate-200',
      ].join(' ')}
    >
      <div className="px-5 py-4">
        {/* Topic + badges row */}
        <div className="flex items-start gap-3 min-w-0">
          <div className="flex-1 min-w-0">
            <p className="text-[15px] font-semibold text-slate-900 leading-snug break-words">{s.display_label ?? s.topic}</p>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <CoverageBadge type={s.coverage_type} />
              {s.status === 'conflict' && <StatusChip status="conflict" />}
              <span className="text-[12px] text-slate-500">{explainGap(s)}</span>
            </div>
          </div>
          {state.tag === 'promoted' && (
            <span className="shrink-0 text-[12px] font-semibold text-emerald-600 mt-0.5">✓ Aplicado</span>
          )}
        </div>

        <GapValueStrip suggestion={s} />

        {/* Conflict notice */}
        {state.tag === 'conflict' && (
          <div className="mt-3 rounded-lg bg-amber-50 border border-amber-100 px-4 py-3 text-[13px] text-amber-700 leading-relaxed">
            Ya existe un documento para este tema. Ignoralo o eliminá el documento para volver a promover.
          </div>
        )}

        {/* Validation error */}
        {state.tag === 'validation_error' && (
          <div className="mt-3 rounded-lg bg-amber-50 border border-amber-100 px-4 py-2.5 text-[13px] text-amber-700">
            {state.reason}
          </div>
        )}

        {/* API error */}
        {state.tag === 'error' && (
          <p className="mt-2 text-[13px] text-red-500">{state.message}</p>
        )}

        {/* Ignored notice */}
        {(state.tag === 'ignoring' || state.tag === 'ignored') && (
          <div className="mt-3 rounded-lg bg-red-50 border border-red-100 px-4 py-2.5 text-[13px] text-red-600 transition-all duration-300 ease-out">
            {state.tag === 'ignoring' ? 'Ignorando gap…' : 'Gap ignorado. Esta accion oculta este tema de la lista.'}
          </div>
        )}

        {/* Draft editor */}
        {state.tag === 'reviewing' && (
          <GapResolutionPanel
            suggestion={s}
            state={state}
            evidenceSnippets={evidenceSnippets}
          />
        )}

        {/* Success feedback */}
        {state.tag === 'promoted' && (
          <div className="mt-3 rounded-lg bg-emerald-50 border border-emerald-100 px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="text-emerald-500 shrink-0">✓</span>
              <p className="text-[13px] text-emerald-700">
                {state.result.chunks_created} fragmentos indexados. El conocimiento ya quedo disponible para futuras respuestas.
              </p>
            </div>
            {state.result.knowledge_impact && (
              <div className="mt-2 text-[13px] text-emerald-800 leading-relaxed">
                <p>{state.result.knowledge_impact.message}</p>
                <p className="mt-1 text-[12px] text-emerald-700">
                  Cobertura: {state.result.knowledge_impact.coverage_before} → {state.result.knowledge_impact.coverage_after}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        {state.tag !== 'reviewing' && (
          <div className="mt-4 flex items-center justify-end gap-2">
            <ItemActions
              suggestion={s}
              state={state}
              onIgnore={onIgnore}
              onUndo={onUndo}
              onClose={() => setItemState(s.topic, { tag: 'idle' })}
              onGenerateDraft={onGenerateDraft}
              onPromote={onPromote}
            />
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Compact medium row ───────────────────────────────────────────────────────

function MediumRow({
  suggestion,
  state,
  editedContent,
  evidenceSnippets,
  focused = false,
  onGenerateDraft,
  onPromote,
  onIgnore,
  onUndo,
  onEditContent,
}: SuggestionItemProps) {
  const s = suggestion

  if (state.tag === 'ignoring' || state.tag === 'ignored') {
    return (
      <div
        className={[
          'border rounded-xl transition-all duration-300 ease-out',
          state.tag === 'ignoring'
            ? 'border-red-200 bg-red-50/70 scale-[0.99]'
            : 'border-red-100 bg-red-50/60',
        ].join(' ')}
      >
        <div className="flex items-center gap-3 px-4 py-3 min-w-0">
          <PriorityDot priority={s.priority} />
          <div className="flex-1 min-w-0">
            <p className="text-[14px] font-medium text-slate-800 truncate leading-tight">{s.display_label ?? s.topic}</p>
            <p className="text-[12px] text-red-500 mt-0.5 leading-tight">
              {state.tag === 'ignoring'
                ? 'Ignorando...'
                : 'Ignorado. Este gap queda oculto hasta deshacer la accion.'}
            </p>
          </div>
          {state.tag === 'ignored' && (
            <button
              onClick={onUndo}
              className="shrink-0 text-[12px] px-2.5 py-1 rounded-md border border-red-200 text-red-600 hover:bg-red-50 transition-colors"
            >
              Deshacer acción
            </button>
          )}
        </div>
      </div>
    )
  }

  const expanded = state.tag === 'reviewing' || state.tag === 'promoted' || state.tag === 'conflict' || state.tag === 'validation_error' || state.tag === 'error'

  return (
    <div
      className={[
        'border rounded-xl transition-all duration-300 ease-out',
        state.tag === 'promoted'
          ? 'border-emerald-200 bg-emerald-50/40'
          : state.tag === 'conflict'
          ? 'border-amber-200 bg-amber-50/30'
          : state.tag === 'ignoring'
          ? 'border-red-200 bg-red-50/70 scale-[0.99]'
          : state.tag === 'ignored'
          ? 'border-red-100 bg-red-50/60'
          : focused
          ? 'border-emerald-300 bg-emerald-50/30'
          : 'border-slate-200 bg-white hover:border-slate-300',
      ].join(' ')}
    >
      {/* Main row */}
      <div className="flex items-center gap-3 px-4 py-3 min-w-0">
        <PriorityDot priority={s.priority} />
        <div className="flex-1 min-w-0">
          <p className="text-[14px] font-medium text-slate-800 truncate leading-tight">{s.display_label ?? s.topic}</p>
          <p className="text-[12px] text-slate-400 mt-0.5 leading-tight">{explainGap(s)}</p>
          <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
            <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-600">{s.occurrences} {consultasLabel(s.occurrences)}</span>
            <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-600">{formatMinutes(s.estimated_time_lost_minutes)} perdidos</span>
            <span className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-700">{formatMinutes(s.estimated_time_saved_if_resolved_minutes)} posibles</span>
          </div>
        </div>
        <div className="shrink-0 hidden sm:flex items-center gap-1.5">
          <CoverageBadge type={s.coverage_type} />
          {s.status === 'conflict' && <StatusChip status="conflict" />}
        </div>
        <div className="shrink-0 flex items-center gap-1.5 ml-2">
          {state.tag === 'promoted' && (
            <span className="text-[12px] font-medium text-emerald-600">✓</span>
          )}
          {state.tag !== 'promoted' && state.tag !== 'reviewing' && (
            <ItemActions
              suggestion={s}
              state={state}
              onIgnore={onIgnore}
              onUndo={onUndo}
              onClose={() => setItemState(s.topic, { tag: 'idle' })}
              onGenerateDraft={onGenerateDraft}
              onPromote={onPromote}
              compact
            />
          )}
        </div>
      </div>

      {/* Expandable area for draft/errors */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-100 pt-3">
          {state.tag === 'conflict' && (
            <p className="text-[13px] text-amber-700 leading-relaxed">
              Ya existe un documento para este tema. Ignoralo o eliminá el documento para volver a promover.
            </p>
          )}
          {state.tag === 'validation_error' && (
            <p className="text-[13px] text-amber-700">{state.reason}</p>
          )}
          {state.tag === 'error' && (
            <p className="text-[13px] text-red-500">{state.message}</p>
          )}
          {state.tag === 'reviewing' && (
            <GapResolutionPanel
              suggestion={s}
              state={state}
              evidenceSnippets={evidenceSnippets}
            />
          )}
          {state.tag === 'promoted' && (
            <div className="text-[13px] text-emerald-700 leading-relaxed">
              <div className="flex items-center gap-2">
                <span>✓</span>
                <span>{state.result.chunks_created} fragmentos indexados</span>
              </div>
              {state.result.knowledge_impact && (
                <p className="mt-1">{state.result.knowledge_impact.message}</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Ignored state */}
      {(state.tag === 'ignoring' || state.tag === 'ignored') && (
        <div className="px-4 pb-3 flex items-center justify-between border-t border-red-100 pt-2.5 transition-all duration-300 ease-out">
          <span className="text-[12px] text-red-500">
            {state.tag === 'ignoring' ? 'Ignorando…' : 'Ignorado'}
          </span>
          <button
            onClick={onUndo}
            className="text-[12px] px-2.5 py-1 rounded-md border border-red-200 text-red-600 hover:bg-red-50 transition-colors"
          >
            Deshacer acción
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Item actions (shared) ────────────────────────────────────────────────────

type SuggestionItemProps = {
  suggestion: Suggestion
  state: ItemStatus
  editedContent: string
  evidenceSnippets: EvidenceSnippet[]
  focused?: boolean
  onGenerateDraft: () => void
  onPromote: () => void
  onIgnore: () => void
  onUndo: () => void
  onClose: () => void
  onEditContent: (v: string) => void
}

function ItemActions({
  suggestion,
  state,
  onIgnore,
  onUndo,
  onGenerateDraft,
  onPromote,
  compact = false,
  onClose,
}: {
  suggestion: Suggestion
  state: ItemStatus
  onIgnore: () => void
  onUndo: () => void
  onGenerateDraft: () => void
  onPromote: () => void
  compact?: boolean
  onClose: () => void
}) {
  const btnBase = compact
    ? 'text-[12px] px-2 py-1 rounded-md transition-colors'
    : 'text-[13px] px-3 py-1.5 rounded-lg transition-colors'

  if (state.tag === 'idle') {
    return (
      <>
        <button
          onClick={onIgnore}
          className={`${btnBase} text-slate-400 hover:text-slate-600`}
        >
          Ignorar
        </button>
        <button
          onClick={onGenerateDraft}
          className={`${btnBase} border border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300 font-medium`}
        >
          {compact ? 'Ver' : 'Ver contexto'}
        </button>
      </>
    )
  }

  if (state.tag === 'generating') {
    return (
      <span className={`${btnBase} text-slate-400 animate-pulse px-3`}>
        Generando…
      </span>
    )
  }

  if (state.tag === 'reviewing') {
    return (
      <button onClick={onClose} className={`${btnBase} text-slate-400 hover:text-slate-600`}>
        Cerrar
      </button>
    )
  }

  if (state.tag === 'promoting') {
    return (
      <span className={`${btnBase} text-slate-400 animate-pulse px-3`}>
        Agregando…
      </span>
    )
  }

  if (state.tag === 'conflict') {
    return (
      <>
        <span className="text-[11px] font-medium text-amber-600 px-2 py-1 rounded bg-amber-50 border border-amber-200">
          Ya existe
        </span>
        <button
          onClick={onIgnore}
          className={`${btnBase} border border-slate-200 text-slate-500 hover:bg-slate-50`}
        >
          Ignorar
        </button>
      </>
    )
  }

  if (state.tag === 'ignoring' || state.tag === 'ignored') {
    return (
      <button
        onClick={onUndo}
        className={`${btnBase} border border-red-200 text-red-600 hover:bg-red-50`}
      >
        Deshacer acción
      </button>
    )
  }

  if (state.tag === 'validation_error') {
    return (
      <button onClick={onIgnore} className={`${btnBase} text-slate-400 hover:text-slate-600`}>
        Ignorar
      </button>
    )
  }

  if (state.tag === 'error') {
    return (
      <button
        onClick={onGenerateDraft}
        className={`${btnBase} border border-red-200 text-red-500 hover:bg-red-50`}
      >
        Reintentar
      </button>
    )
  }

  return null
}

// ─── Section header ───────────────────────────────────────────────────────────

function SectionHeader({
  label,
  count,
  dotColor,
  right,
}: {
  label: string
  count: number
  dotColor: string
  right?: React.ReactNode
}) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
      <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">{label}</h2>
      <span className="text-xs text-slate-300">({count})</span>
      {right && <div className="ml-auto">{right}</div>}
    </div>
  )
}

// ─── Chevron icon ─────────────────────────────────────────────────────────────

function IconChevron({ open }: { open: boolean }) {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      style={{ transition: 'transform 200ms', transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}

// ─── Low-quality section ──────────────────────────────────────────────────────

function LowQualitySection({
  items,
  open,
  onToggle,
  fadingOut,
  onIgnore,
}: {
  items: Suggestion[]
  open: boolean
  onToggle: () => void
  fadingOut: Set<string>
  onIgnore: (topic: string) => void
}) {
  if (items.length === 0) return null
  return (
    <section className="mt-5 border-t border-slate-100 pt-5">
      <button
        onClick={onToggle}
        className="flex items-center gap-2 w-full text-left group mb-3"
      >
        <span className="w-2 h-2 rounded-full bg-slate-300 shrink-0" />
        <span className="text-xs font-semibold uppercase tracking-widest text-slate-400 group-hover:text-slate-600 transition-colors">
          Baja calidad
        </span>
        <span className="text-xs text-slate-300">({items.length})</span>
        <span className="ml-auto text-slate-300 group-hover:text-slate-400 transition-colors">
          <IconChevron open={open} />
        </span>
      </button>
      {open && (
        <div className="space-y-1.5">
          {items.map(item => (
            <FadingWrapper key={item.topic} fading={fadingOut.has(item.topic)}>
              <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg border border-slate-100 bg-white">
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] text-slate-500 truncate">{item.display_label ?? item.topic}</p>
                  <p className="text-[11px] text-slate-400">{item.occurrences} vez · baja calidad</p>
                </div>
                <button
                  onClick={() => onIgnore(item.topic)}
                  className="text-[12px] px-2 py-1 text-slate-400 hover:text-slate-600 transition-colors shrink-0"
                >
                  Ignorar
                </button>
              </div>
            </FadingWrapper>
          ))}
        </div>
      )}
    </section>
  )
}

// ─── Recently applied ─────────────────────────────────────────────────────────

function RecentlyApplied({
  items,
  open,
  onToggle,
}: {
  items: AppliedItem[]
  open: boolean
  onToggle: () => void
}) {
  if (items.length === 0) return null
  return (
    <section className="mt-5 border-t border-slate-100 pt-5">
      <button
        onClick={onToggle}
        className="flex items-center gap-2 w-full text-left group mb-3"
      >
        <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
        <span className="text-xs font-semibold uppercase tracking-widest text-slate-500 group-hover:text-slate-700 transition-colors">
          Aplicados recientemente
        </span>
        <span className="text-xs text-slate-300">({items.length})</span>
        <span className="ml-auto text-slate-400 group-hover:text-slate-600 transition-colors">
          <IconChevron open={open} />
        </span>
      </button>
      {open && (
        <div className="space-y-1.5">
          {items.map(item => (
            <div
              key={item.topic}
              className="flex items-center gap-3 px-4 py-2.5 rounded-xl border border-slate-100 bg-white"
            >
              <span className="text-emerald-500 shrink-0 text-sm">✓</span>
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium text-slate-700 truncate">{item.display_label ?? item.topic}</p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  {item.chunks_created} fragmentos · {item.coverage_type === 'none' ? 'sin cobertura' : 'parcial'} → documentado · {formatMinutes(item.estimated_time_saved_if_resolved_minutes)} recuperables
                </p>
              </div>
              <DocumentedBadge />
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function ImprovementPage() {
  const searchParams = useSearchParams()
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [insights, setInsights] = useState<Insights | null>(null)
  const [quickWins, setQuickWins] = useState<QuickWin[]>([])
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(false)
  const [itemStates, setItemStates] = useState<Record<string, ItemStatus>>({})
  const [draftEdits, setDraftEdits] = useState<Record<string, string>>({})
  const [fadingOut, setFadingOut] = useState<Set<string>>(new Set())
  const [recentlyApplied, setRecentlyApplied] = useState<AppliedItem[]>([])
  const [showApplied, setShowApplied] = useState(true)
  const [showLowQuality, setShowLowQuality] = useState(false)
  const [sort, setSort] = useState<SortKey>('impact')
  const undoTimers = useState<Record<string, ReturnType<typeof setTimeout>>>(() => ({}))[0]
  const ignoringTimers = useState<Record<string, ReturnType<typeof setTimeout>>>(() => ({}))[0]
  const focusTopic = searchParams.get('focus')

  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/internal/action-suggestions`, { headers: HEADERS }).then(r =>
        r.ok ? r.json() : Promise.reject()
      ),
      fetch(`${API_URL}/internal/knowledge-insights`, { headers: HEADERS }).then(r =>
        r.ok ? r.json() : null
      ),
    ])
      .then(([suggestionsData, insightsData]) => {
        const serverSuggestions: Suggestion[] = suggestionsData.suggestions ?? []
        setSuggestions(serverSuggestions)
        setRecentlyApplied(suggestionsData.recently_applied ?? [])
        setQuickWins(suggestionsData.quick_wins ?? [])
        setRecommendations(suggestionsData.recommendations ?? [])
        if (insightsData) setInsights(insightsData)

        const initial: Record<string, ItemStatus> = {}
        for (const s of serverSuggestions) {
          if (s.status === 'conflict') {
            initial[s.topic] = { tag: 'conflict' }
          }
        }
        if (Object.keys(initial).length > 0) setItemStates(initial)

        const edits: Record<string, string> = {}
        for (const s of serverSuggestions) {
          if (s.draft_content) edits[s.topic] = sanitizeDraftContent(s.draft_content)
        }
        if (Object.keys(edits).length > 0) setDraftEdits(edits)

        setLoading(false)
      })
      .catch(() => {
        setFetchError(true)
        setLoading(false)
      })
  }, [])

  function getState(topic: string): ItemStatus {
    return itemStates[topic] ?? { tag: 'idle' }
  }

  function setItemState(topic: string, state: ItemStatus) {
    setItemStates(prev => ({ ...prev, [topic]: state }))
  }

  function dismiss(topic: string, delayMs = 0) {
    setTimeout(() => {
      setFadingOut(prev => new Set([...prev, topic]))
      setTimeout(() => {
        setSuggestions(prev => prev.filter(s => s.topic !== topic))
        setFadingOut(prev => { const n = new Set(prev); n.delete(topic); return n })
        setItemStates(prev => { const n = { ...prev }; delete n[topic]; return n })
        setDraftEdits(prev => { const n = { ...prev }; delete n[topic]; return n })
      }, 350)
    }, delayMs)
  }

  async function handleIgnore(topic: string) {
    try {
      await fetch(`${API_URL}/internal/action-suggestions/ignore`, {
        method: 'POST',
        headers: HEADERS,
        body: JSON.stringify({ topic }),
      })
    } catch {}
    if (undoTimers[topic]) {
      clearTimeout(undoTimers[topic])
      delete undoTimers[topic]
    }
    if (ignoringTimers[topic]) {
      clearTimeout(ignoringTimers[topic])
      delete ignoringTimers[topic]
    }
    setItemState(topic, { tag: 'ignoring' })
    ignoringTimers[topic] = setTimeout(() => {
      setItemState(topic, { tag: 'ignored' })
      delete ignoringTimers[topic]
    }, 280)
    const timer = setTimeout(() => dismiss(topic), 5000)
    undoTimers[topic] = timer
  }

  async function handleUndo(topic: string) {
    if (undoTimers[topic]) {
      clearTimeout(undoTimers[topic])
      delete undoTimers[topic]
    }
    if (ignoringTimers[topic]) {
      clearTimeout(ignoringTimers[topic])
      delete ignoringTimers[topic]
    }
    try {
      const res = await fetch(`${API_URL}/internal/action-suggestions/undo`, {
        method: 'POST',
        headers: HEADERS,
        body: JSON.stringify({ topic }),
      })
      if (!res.ok) throw new Error()
    } catch {}
    setItemState(topic, { tag: 'idle' })
  }

  async function handleGenerateDraft(topic: string) {
    const validation = isTopicValid(topic)
    if (!validation.valid) {
      setItemState(topic, { tag: 'validation_error', reason: validation.reason! })
      return
    }
    setItemState(topic, { tag: 'reviewing' })
  }

  async function handlePromote(suggestion: Suggestion) {
    const current = getState(suggestion.topic)
    if (current.tag !== 'draft_ready') return
    const { draft } = current
    const contentToPromote = draftEdits[suggestion.topic] ?? draft.draft_content

    setItemState(suggestion.topic, { tag: 'promoting', draft })
    try {
      const res = await fetch(`${API_URL}/internal/action-suggestions/promote`, {
        method: 'POST',
        headers: HEADERS,
        body: JSON.stringify({ topic: suggestion.topic, draft_content: contentToPromote }),
      })

      if (res.status === 409) {
        setItemState(suggestion.topic, { tag: 'conflict', draft })
        return
      }
      if (!res.ok) throw new Error()

      const result: PromoteResult = await res.json()
      setItemState(suggestion.topic, { tag: 'promoted', draft, result })
      setRecentlyApplied(prev =>
        [
          {
            topic: suggestion.topic,
            display_label: suggestion.display_label,
            coverage_type: suggestion.coverage_type,
            chunks_created: result.chunks_created,
            promoted_at: result.promoted_at,
            occurrences: result.knowledge_impact?.affected_occurrences ?? suggestion.occurrences,
            estimated_time_saved_if_resolved_minutes:
              result.knowledge_impact?.estimated_time_saved_if_resolved_minutes
              ?? suggestion.estimated_time_saved_if_resolved_minutes,
          },
          ...prev,
        ].slice(0, 5)
      )
      dismiss(suggestion.topic, 4500)
    } catch {
      setItemState(suggestion.topic, { tag: 'error', message: 'No se pudo promover el borrador.' })
    }
  }

  // ── Sorted and split ──────────────────────────────────────────────────────

  const allSorted = sortSuggestions(suggestions, sort).sort((a, b) => {
    if (!focusTopic) return 0
    if (a.topic === focusTopic) return -1
    if (b.topic === focusTopic) return 1
    return 0
  })
  const highPriority = allSorted.filter(s => s.priority === 'high')
  const mediumPriority = allSorted.filter(s => s.priority === 'medium')
  const lowQuality = allSorted.filter(s => s.priority === 'low_quality')
  const isEmpty = !loading && !fetchError && suggestions.length === 0

  function makeItemProps(s: Suggestion): SuggestionItemProps {
    return {
      suggestion: s,
      state: getState(s.topic),
      editedContent: draftEdits[s.topic] ?? '',
      evidenceSnippets: backendEvidenceSnippets(s),
      focused: s.topic === focusTopic,
      onGenerateDraft: () => handleGenerateDraft(s.topic),
      onPromote: () => handlePromote(s),
      onIgnore: () => handleIgnore(s.topic),
      onUndo: () => handleUndo(s.topic),
      onEditContent: v => setDraftEdits(prev => ({ ...prev, [s.topic]: v })),
    }
  }

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto bg-slate-50">
        <main className="max-w-4xl mx-auto px-4 py-8 sm:px-6">

          {/* Page header */}
          <div className="mb-5">
            <h1 className="text-xl font-semibold text-slate-900 tracking-tight">Gaps de conocimiento</h1>
            <p className="text-[14px] text-slate-500 mt-1 leading-relaxed">
              Consultas sin respuesta o con cobertura incompleta. Revisá la propuesta, editála si hace falta y agregala al conocimiento para cerrar el gap.
            </p>
            <p className="text-[12px] text-slate-400 mt-2">
              Estimación actual: cobertura nula = 3 min perdidos por consulta, cobertura parcial = 2 min.
            </p>
          </div>

          {/* Quick wins + insights */}
          {!loading && !fetchError && (
            <>
              <QuickWinsPanel items={quickWins} />
              <BusinessInsightsBar insights={insights} />
              <RecommendationsPanel items={recommendations} />
            </>
          )}

          {/* Loading */}
          {loading && (
            <div className="space-y-2.5">
              {[0, 1, 2, 3].map(i => (
                <div key={i} className="h-16 bg-white border border-slate-200 rounded-xl animate-pulse" />
              ))}
            </div>
          )}

          {/* Error */}
          {!loading && fetchError && (
            <div className="border border-red-200 bg-red-50 rounded-xl p-6 text-center">
              <p className="text-[15px] font-medium text-red-600">No se pudo conectar con el backend.</p>
              <p className="text-[13px] text-red-400 mt-1">Verificá que el servidor esté corriendo en {API_URL}</p>
            </div>
          )}

          {/* Empty */}
          {isEmpty && recentlyApplied.length === 0 && (
            <div className="border border-slate-200 bg-white rounded-xl p-12 text-center">
              <div className="w-12 h-12 rounded-2xl bg-emerald-50 flex items-center justify-center mx-auto mb-4">
                <span className="text-emerald-500 text-xl">✓</span>
              </div>
              <p className="text-[15px] font-semibold text-slate-700">Todo el conocimiento está cubierto</p>
              <p className="text-[13px] text-slate-400 mt-2 max-w-xs mx-auto leading-relaxed">
                No hay consultas sin respuesta. Los gaps aparecerán acá automáticamente cuando el chat detecte preguntas sin cobertura.
              </p>
            </div>
          )}

          {/* Content: sort + sections */}
          {!loading && !fetchError && suggestions.length > 0 && (
            <>
              {/* Sort controls */}
              <div className="flex items-center justify-between mb-5">
                <SortControls sort={sort} onChange={setSort} />
                <span className="text-[12px] text-slate-400">
                  {mediumPriority.length + highPriority.length} gap{mediumPriority.length + highPriority.length !== 1 ? 's' : ''} activo{mediumPriority.length + highPriority.length !== 1 ? 's' : ''}
                </span>
              </div>

              {/* High priority */}
              {highPriority.length > 0 && (
                <section className="mb-7">
                  <SectionHeader label="Alta prioridad" count={highPriority.length} dotColor="bg-red-500" />
                  <div className="space-y-3">
                    {highPriority.map(s => (
                      <FadingWrapper key={s.topic} fading={fadingOut.has(s.topic)}>
                        <HighPriorityCard {...makeItemProps(s)} />
                      </FadingWrapper>
                    ))}
                  </div>
                </section>
              )}

              {/* Medium priority */}
              {mediumPriority.length > 0 && (
                <section className="mb-7">
                  <SectionHeader label="Prioridad media" count={mediumPriority.length} dotColor="bg-amber-400" />
                  <div className="space-y-2">
                    {mediumPriority.map(s => (
                      <FadingWrapper key={s.topic} fading={fadingOut.has(s.topic)}>
                        <MediumRow {...makeItemProps(s)} />
                      </FadingWrapper>
                    ))}
                  </div>
                </section>
              )}

              {/* Low quality */}
              <LowQualitySection
                items={lowQuality}
                open={showLowQuality}
                onToggle={() => setShowLowQuality(v => !v)}
                fadingOut={fadingOut}
                onIgnore={handleIgnore}
              />

              {/* Recently applied */}
              <RecentlyApplied
                items={recentlyApplied}
                open={showApplied}
                onToggle={() => setShowApplied(v => !v)}
              />
            </>
          )}

          {/* Empty but with recently applied */}
          {isEmpty && recentlyApplied.length > 0 && (
            <>
              <div className="border border-emerald-200 bg-emerald-50 rounded-xl px-5 py-4 mb-6 flex items-center gap-3">
                <span className="text-emerald-500 text-lg">✓</span>
                <p className="text-[14px] font-medium text-emerald-700">
                  No quedan gaps activos. Seguí usando el chat para detectar nuevas oportunidades.
                </p>
              </div>
              <RecentlyApplied
                items={recentlyApplied}
                open={showApplied}
                onToggle={() => setShowApplied(v => !v)}
              />
            </>
          )}

        </main>
      </div>
    </AppShell>
  )
}
