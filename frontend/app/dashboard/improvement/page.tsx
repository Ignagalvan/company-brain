'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ORG_ID = process.env.NEXT_PUBLIC_ORG_ID ?? '00000000-0000-0000-0000-000000000001'
const HEADERS = {
  'Content-Type': 'application/json',
  'X-Organization-Id': ORG_ID,
}

// ─── Types ────────────────────────────────────────────────────────────────────

type Suggestion = {
  topic: string
  coverage_type: 'none' | 'partial'
  priority: 'high' | 'medium'
  occurrences: number
  avg_coverage_score: number
  suggested_action: 'create_document' | 'improve_document'
  has_existing_draft: boolean
  ready_for_draft: boolean
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
}

type ItemStatus =
  | { tag: 'idle' }
  | { tag: 'generating' }
  | { tag: 'draft_ready'; draft: Draft }
  | { tag: 'promoting'; draft: Draft }
  | { tag: 'promoted'; draft: Draft; result: PromoteResult }
  | { tag: 'conflict'; draft: Draft }
  | { tag: 'error'; message: string }

// ─── Small components ─────────────────────────────────────────────────────────

function CoverageBadge({ type }: { type: 'none' | 'partial' }) {
  if (type === 'none') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-red-50 text-red-600 border border-red-100">
        <span className="w-1.5 h-1.5 rounded-full bg-red-500 inline-block" />
        Sin cobertura
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-600 border border-amber-100">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />
      Cobertura parcial
    </span>
  )
}

function PriorityDot({ priority }: { priority: 'high' | 'medium' }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${
        priority === 'high' ? 'bg-red-400' : 'bg-amber-400'
      }`}
      title={priority === 'high' ? 'Prioridad alta' : 'Prioridad media'}
    />
  )
}

function DraftPreview({ draft }: { draft: Draft }) {
  return (
    <div className="mt-4 border border-slate-200 rounded-lg overflow-hidden">
      <div className="bg-slate-50 border-b border-slate-200 px-4 py-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          Borrador generado
        </span>
        <span className="text-xs text-slate-400 font-mono">{draft.draft_type}</span>
      </div>
      <pre className="p-4 text-xs text-slate-700 leading-relaxed whitespace-pre-wrap font-mono overflow-auto max-h-52 bg-white">
        {draft.draft_content}
      </pre>
    </div>
  )
}

function ActionResult({
  result,
  coverageBefore,
}: {
  result: PromoteResult
  coverageBefore: 'none' | 'partial'
}) {
  return (
    <div className="mt-4 border border-emerald-200 rounded-lg bg-emerald-50 p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-emerald-600 text-lg">✓</span>
        <span className="text-sm font-semibold text-emerald-800">Mejora aplicada</span>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white rounded-md border border-emerald-100 px-3 py-2">
          <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">Cobertura</p>
          <p className="text-sm font-medium text-slate-700">
            <span className="text-red-500">{coverageBefore === 'none' ? 'ninguna' : 'parcial'}</span>
            {' → '}
            <span className="text-emerald-600">documentado</span>
          </p>
        </div>
        <div className="bg-white rounded-md border border-emerald-100 px-3 py-2">
          <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">Chunks</p>
          <p className="text-sm font-semibold text-emerald-700">{result.chunks_created} creados</p>
        </div>
        <div className="bg-white rounded-md border border-emerald-100 px-3 py-2">
          <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">Estado</p>
          <p className="text-sm font-medium text-emerald-700">Disponible para retrieval</p>
        </div>
      </div>
      <p className="mt-2 text-[11px] text-slate-400 font-mono truncate">{result.filename}</p>
    </div>
  )
}

// ─── Suggestion item ──────────────────────────────────────────────────────────

function SuggestionItem({
  suggestion,
  state,
  onGenerateDraft,
  onPromote,
}: {
  suggestion: Suggestion
  state: ItemStatus
  onGenerateDraft: () => void
  onPromote: () => void
}) {
  const isPromoted = state.tag === 'promoted'
  const isConflict = state.tag === 'conflict'

  return (
    <div
      className={`border rounded-xl p-4 transition-all ${
        isPromoted
          ? 'border-emerald-200 bg-emerald-50/30'
          : 'border-slate-200 bg-white hover:border-slate-300'
      }`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-2 min-w-0">
          <PriorityDot priority={suggestion.priority} />
          <div className="min-w-0">
            <p className="text-sm font-medium text-slate-800 leading-tight truncate">
              {suggestion.topic}
            </p>
            <div className="flex items-center gap-2 mt-1">
              <CoverageBadge type={suggestion.coverage_type} />
              <span className="text-[11px] text-slate-400">
                {suggestion.occurrences} {suggestion.occurrences === 1 ? 'consulta' : 'consultas'}
              </span>
              {suggestion.has_existing_draft && (
                <span className="text-[11px] text-slate-400 italic">· ya tiene borrador</span>
              )}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 shrink-0">
          {state.tag === 'idle' && (
            <button
              onClick={onGenerateDraft}
              className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300 transition-colors font-medium"
            >
              Generar draft
            </button>
          )}

          {state.tag === 'generating' && (
            <span className="text-xs text-slate-400 px-3 py-1.5 animate-pulse">
              Generando…
            </span>
          )}

          {state.tag === 'draft_ready' && (
            <>
              <button
                onClick={onGenerateDraft}
                className="text-xs px-2 py-1.5 text-slate-400 hover:text-slate-600 transition-colors"
              >
                Regenerar
              </button>
              <button
                onClick={onPromote}
                className="text-xs px-3 py-1.5 rounded-lg bg-slate-900 text-white hover:bg-slate-700 transition-colors font-medium"
              >
                Promover solución →
              </button>
            </>
          )}

          {state.tag === 'promoting' && (
            <span className="text-xs text-slate-400 px-3 py-1.5 animate-pulse">
              Promoviendo…
            </span>
          )}

          {isPromoted && (
            <span className="text-xs text-emerald-600 font-medium px-3 py-1.5">
              ✓ Aplicado
            </span>
          )}

          {isConflict && (
            <span className="text-xs text-amber-600 font-medium px-3 py-1.5">
              Ya existe
            </span>
          )}

          {state.tag === 'error' && (
            <button
              onClick={onGenerateDraft}
              className="text-xs px-3 py-1.5 rounded-lg border border-red-200 text-red-500 hover:bg-red-50 transition-colors"
            >
              Reintentar
            </button>
          )}
        </div>
      </div>

      {/* Draft preview */}
      {(state.tag === 'draft_ready' || state.tag === 'promoting') && (
        <DraftPreview draft={state.draft} />
      )}

      {/* Promote result */}
      {isPromoted && (
        <ActionResult result={state.result} coverageBefore={suggestion.coverage_type} />
      )}

      {/* Conflict notice */}
      {isConflict && (
        <div className="mt-3 rounded-lg bg-amber-50 border border-amber-100 px-4 py-3 text-xs text-amber-700">
          Ya existe un documento para este tema en tu base de conocimiento. Eliminalo si querés reemplazarlo.
        </div>
      )}

      {/* Error */}
      {state.tag === 'error' && (
        <p className="mt-2 text-xs text-red-500">{state.message}</p>
      )}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function ImprovementPage() {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [promoted, setPromoted] = useState<Suggestion[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(false)
  const [itemStates, setItemStates] = useState<Record<string, ItemStatus>>({})

  useEffect(() => {
    fetch(`${API_URL}/internal/action-suggestions`, { headers: HEADERS })
      .then(r => (r.ok ? r.json() : Promise.reject()))
      .then(data => {
        setSuggestions(data.suggestions ?? [])
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

  async function handleGenerateDraft(topic: string) {
    setItemState(topic, { tag: 'generating' })
    try {
      const res = await fetch(`${API_URL}/internal/action-suggestions/draft`, {
        method: 'POST',
        headers: HEADERS,
        body: JSON.stringify({ topic }),
      })
      if (!res.ok) throw new Error()
      const draft: Draft = await res.json()
      setItemState(topic, { tag: 'draft_ready', draft })
    } catch {
      setItemState(topic, { tag: 'error', message: 'No se pudo generar el borrador.' })
    }
  }

  async function handlePromote(suggestion: Suggestion) {
    const current = getState(suggestion.topic)
    if (current.tag !== 'draft_ready') return
    const { draft } = current

    setItemState(suggestion.topic, { tag: 'promoting', draft })
    try {
      const res = await fetch(`${API_URL}/internal/action-suggestions/promote`, {
        method: 'POST',
        headers: HEADERS,
        body: JSON.stringify({ topic: suggestion.topic }),
      })

      if (res.status === 409) {
        setItemState(suggestion.topic, { tag: 'conflict', draft })
        return
      }
      if (!res.ok) throw new Error()

      const result: PromoteResult = await res.json()
      setItemState(suggestion.topic, { tag: 'promoted', draft, result })

      // Move to promoted list, remove from active
      setSuggestions(prev => prev.filter(s => s.topic !== suggestion.topic))
      setPromoted(prev => [suggestion, ...prev])
    } catch {
      setItemState(suggestion.topic, {
        tag: 'error',
        message: 'No se pudo promover el borrador.',
      })
    }
  }

  const highPriority = suggestions.filter(s => s.priority === 'high')
  const mediumPriority = suggestions.filter(s => s.priority === 'medium')

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      {/* Header */}
      <header className="bg-white border-b border-slate-100 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-6 h-12 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/app"
              className="text-sm font-semibold text-slate-900 hover:text-slate-500 transition-colors"
            >
              Company Brain
            </Link>
            <span className="text-slate-300">/</span>
            <span className="text-sm text-slate-500 font-medium">Knowledge Improvement</span>
          </div>
          <Link
            href="/app"
            className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
          >
            ← Chat
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        {/* Page title */}
        <div className="mb-8">
          <h1 className="text-lg font-semibold text-slate-900">Gaps de conocimiento</h1>
          <p className="text-sm text-slate-500 mt-1">
            Consultas sin respuesta detectadas en tu base de conocimiento. Generá un borrador y promovelo para cerrar el gap.
          </p>
        </div>

        {/* Loading */}
        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 bg-white border border-slate-200 rounded-xl animate-pulse" />
            ))}
          </div>
        )}

        {/* Error */}
        {!loading && fetchError && (
          <div className="border border-red-200 bg-red-50 rounded-xl p-6 text-center">
            <p className="text-sm text-red-600 font-medium">No se pudo conectar con el backend.</p>
            <p className="text-xs text-red-400 mt-1">
              Verificá que el servidor esté corriendo en {API_URL}
            </p>
          </div>
        )}

        {/* Empty */}
        {!loading && !fetchError && suggestions.length === 0 && promoted.length === 0 && (
          <div className="border border-slate-200 bg-white rounded-xl p-10 text-center">
            <p className="text-sm font-medium text-slate-700">Sin gaps detectados</p>
            <p className="text-xs text-slate-400 mt-1">
              Hacé algunas consultas en el chat y volvé acá para ver los temas sin cobertura.
            </p>
          </div>
        )}

        {/* High priority */}
        {!loading && highPriority.length > 0 && (
          <section className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-2 h-2 rounded-full bg-red-400 inline-block" />
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Alta prioridad
              </h2>
              <span className="text-xs text-slate-300">({highPriority.length})</span>
            </div>
            <div className="space-y-3">
              {highPriority.map(s => (
                <SuggestionItem
                  key={s.topic}
                  suggestion={s}
                  state={getState(s.topic)}
                  onGenerateDraft={() => handleGenerateDraft(s.topic)}
                  onPromote={() => handlePromote(s)}
                />
              ))}
            </div>
          </section>
        )}

        {/* Medium priority */}
        {!loading && mediumPriority.length > 0 && (
          <section className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Prioridad media
              </h2>
              <span className="text-xs text-slate-300">({mediumPriority.length})</span>
            </div>
            <div className="space-y-3">
              {mediumPriority.map(s => (
                <SuggestionItem
                  key={s.topic}
                  suggestion={s}
                  state={getState(s.topic)}
                  onGenerateDraft={() => handleGenerateDraft(s.topic)}
                  onPromote={() => handlePromote(s)}
                />
              ))}
            </div>
          </section>
        )}

        {/* Promoted this session */}
        {promoted.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-3">
              <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Aplicados esta sesión
              </h2>
              <span className="text-xs text-slate-300">({promoted.length})</span>
            </div>
            <div className="space-y-3">
              {promoted.map(s => (
                <SuggestionItem
                  key={s.topic}
                  suggestion={s}
                  state={getState(s.topic)}
                  onGenerateDraft={() => handleGenerateDraft(s.topic)}
                  onPromote={() => handlePromote(s)}
                />
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  )
}
