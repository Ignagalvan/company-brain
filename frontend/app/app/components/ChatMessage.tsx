'use client'

import { useState } from 'react'
import { Message } from '../types'

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

  return (
    <div className="flex justify-start">
      <div className="max-w-2xl w-full space-y-2">

        {/* Answer card */}
        <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm shadow-sm">
          <div className="flex items-center justify-between px-5 pt-3.5 pb-0">
            <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
              Respuesta
            </span>
            <button
              onClick={handleCopy}
              className="text-[11px] text-slate-400 hover:text-slate-600 px-2 py-1 rounded-md hover:bg-slate-50 transition-colors"
            >
              {copied ? '✓ Copiado' : 'Copiar'}
            </button>
          </div>
          <div className="px-5 py-4">
            <p className="text-sm text-slate-800 leading-7">{msg.content}</p>
          </div>
        </div>

        {/* Citations toggle */}
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
              <div className="mt-2 space-y-1.5">
                {msg.citations.map((citation, idx) => (
                  <div key={citation.id} className="bg-white border border-slate-100 rounded-xl px-4 py-3">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="shrink-0 w-4 h-4 rounded bg-slate-100 flex items-center justify-center text-[9px] font-bold text-slate-500">
                        {idx + 1}
                      </span>
                      <span className="text-[10px] text-slate-400 bg-slate-50 border border-slate-100 px-1.5 py-px rounded-md">
                        fragmento {citation.chunk_index}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 leading-relaxed line-clamp-3">
                      {citation.content}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
