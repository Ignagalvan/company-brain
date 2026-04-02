'use client'

import { useState } from 'react'
import { Message } from '../types'

function cleanFilename(raw: string): string {
  const match = raw.match(/^[0-9a-f-]{36}_(.+)$/i)
  return match ? match[1] : raw
}

export function ChatMessage({ msg }: { msg: Message }) {
  const [copied, setCopied] = useState(false)
  const [showSources, setShowSources] = useState(false)

  if (msg.type === 'user') {
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

  const hasSources = msg.sources && msg.sources.length > 0

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

        {/* Sources toggle */}
        {hasSources && (
          <div className="pl-1">
            <button
              onClick={() => setShowSources(v => !v)}
              className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 hover:text-slate-600 transition-colors px-1 py-0.5"
            >
              <span className="text-[9px]">{showSources ? '▾' : '▸'}</span>
              {showSources
                ? 'Ocultar fuentes'
                : `Ver fuentes (${msg.sources!.length})`}
            </button>

            {showSources && (
              <div className="mt-2 space-y-1.5">
                {msg.sources!.map((src, idx) => (
                  <div key={src.chunk_id} className="bg-white border border-slate-100 rounded-xl px-4 py-3">
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="shrink-0 w-4 h-4 rounded bg-slate-100 flex items-center justify-center text-[9px] font-bold text-slate-500">
                          {idx + 1}
                        </span>
                        <span className="text-xs font-medium text-slate-700 truncate">
                          {cleanFilename(src.filename)}
                        </span>
                        <span className="shrink-0 text-[10px] text-slate-400 bg-slate-50 border border-slate-100 px-1.5 py-px rounded-md">
                          frag. {src.chunk_index}
                        </span>
                      </div>
                      <span className="shrink-0 ml-3 text-[10px] text-slate-400 tabular-nums">
                        {src.distance.toFixed(3)}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 leading-relaxed line-clamp-3">
                      {src.content}
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
