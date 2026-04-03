'use client'

import { useState } from 'react'
import { Message } from '../types'

function cleanFilename(raw: string): string {
  const match = raw.match(/^[0-9a-f-]{36}_(.+)$/i)
  return match ? match[1] : raw
}

function EvidenceBadge({ msg }: { msg: Message }) {
  if (msg.has_sufficient_evidence) {
    return (
      <div className="space-y-1">
        <div className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 px-2.5 py-1 rounded-full">
          <span>✓</span> Evidencia suficiente
        </div>
        <p className="text-[11px] text-slate-500">
          Basado en {msg.sources_count} fragmentos de {msg.documents_count} documento{msg.documents_count !== 1 ? 's' : ''}
        </p>
      </div>
    )
  }

  if (msg.is_partial_answer) {
    return (
      <div className="space-y-1">
        <div className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-100 px-2.5 py-1 rounded-full">
          <span>◐</span> Evidencia parcial
        </div>
        <p className="text-[11px] text-slate-500">
          Respuesta parcial basada en evidencia limitada ({msg.sources_count} fragmento{msg.sources_count !== 1 ? 's' : ''} encontrado{msg.sources_count !== 1 ? 's' : ''})
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      <div className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-slate-500 bg-slate-100 border border-slate-200 px-2.5 py-1 rounded-full">
        <span>○</span> Sin evidencia
      </div>
      <p className="text-[11px] text-slate-500">
        No se encontró evidencia en los documentos disponibles
      </p>
    </div>
  )
}

export function ChatMessage({ msg }: { msg: Message }) {
  const [copied, setCopied] = useState(false)
  const [showCitations, setShowCitations] = useState(false)

  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-xl bg-slate-900 text-white rounded-2xl rounded-tr-sm px-5 py-3.5">
          <p className="text-sm leading-relaxed">{msg.content}</p>
        </div>
      </div>
    )
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(msg.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {}
  }

  const hasCitations = msg.citations && msg.citations.length > 0
  const showDebug = process.env.NODE_ENV === 'development' && !!msg.debug

  return (
    <div className="flex justify-start">
      <div className="max-w-2xl w-full space-y-2">

        {/* Answer card */}
        <div className="animate-fade-slide-in bg-white border border-slate-200 rounded-2xl rounded-tl-sm shadow-sm">
          <div className="flex items-center justify-between px-5 pt-3.5 pb-0">
            <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
              Respuesta
            </span>
            <button
              onClick={handleCopy}
              className="text-[11px] text-slate-400 hover:text-slate-600 px-2 py-1 rounded-md hover:bg-slate-100 transition-colors"
            >
              {copied ? '✓ Copiado' : 'Copiar'}
            </button>
          </div>
          <div className="px-5 py-4">
            <p className="text-sm text-slate-800 leading-7">{msg.content}</p>
          </div>
          <div className="px-5 pb-4">
            <EvidenceBadge msg={msg} />
          </div>
        </div>

        {/* Citations */}
        {hasCitations && (
          <div className="pl-1">
            <button
              onClick={() => setShowCitations(v => !v)}
              className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 hover:text-slate-600 transition-colors px-1 py-0.5"
            >
              <span className="text-[9px]">{showCitations ? '▾' : '▸'}</span>
              {showCitations
                ? 'Ocultar fuentes'
                : `Ver fuentes (${msg.citations.length})`}
            </button>

            {showCitations && (
              <div className="mt-2 space-y-2">
                {msg.citations.map((citation, idx) => (
                  <div key={citation.id} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                    <div className="flex items-center gap-2 px-4 py-2.5 bg-slate-50 border-b border-slate-100">
                      <span className="shrink-0 w-5 h-5 rounded-full bg-slate-200 flex items-center justify-center text-[10px] font-bold text-slate-600">
                        {idx + 1}
                      </span>
                      <span className="text-xs font-medium text-slate-700 truncate flex-1">
                        {citation.filename ? cleanFilename(citation.filename) : 'Documento'}
                      </span>
                      <span className="shrink-0 text-[10px] text-slate-400 bg-white border border-slate-200 px-2 py-0.5 rounded-md">
                        fragmento {citation.chunk_index}
                      </span>
                    </div>
                    <div className="px-4 py-3">
                      <p className="text-[12px] text-slate-600 leading-relaxed line-clamp-4">
                        {citation.content}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Debug panel — visible only in development when backend has debug=true */}
        {showDebug && msg.debug && (
          <div className="mt-1 p-3 bg-slate-900 rounded-xl font-mono text-[10px] text-slate-300 space-y-1.5">
            <p className="text-slate-400 font-semibold uppercase tracking-widest text-[9px]">Debug</p>
            <p>
              chunks: <span className="text-white">{msg.debug.raw_chunks_count}</span> totales
              {' / '}
              <span className="text-white">{msg.debug.relevant_chunks_count}</span> relevantes
            </p>
            <p>
              fallback:{' '}
              {msg.debug.fallback
                ? <span className="text-amber-400">{msg.debug.fallback_reason ?? 'sí'}</span>
                : <span className="text-emerald-400">no</span>}
            </p>
            <div>
              <p className="text-slate-500 mb-0.5">distances:</p>
              <div className="pl-2 space-y-0.5">
                {msg.debug.distances.map((d, i) => (
                  <p key={i}>
                    frag {d.chunk_index}:{' '}
                    <span className={d.distance <= 0.45 ? 'text-emerald-400' : 'text-red-400'}>
                      {d.distance}
                    </span>
                  </p>
                ))}
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
