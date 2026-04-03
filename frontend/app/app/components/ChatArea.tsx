'use client'

import { useEffect, useRef, useState } from 'react'
import { Conversation } from '../types'
import { ChatMessage } from './ChatMessage'

interface ChatAreaProps {
  conversation: Conversation | null
  pendingContent: string
  sendError: string
  onSend: (content: string) => void
}

export function ChatArea({ conversation, pendingContent, sendError, onSend }: ChatAreaProps) {
  const [input, setInput] = useState('')
  const chatEndRef = useRef<HTMLDivElement>(null)
  const isSending = pendingContent !== ''

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation?.messages.length, pendingContent])

  function handleSubmit() {
    const content = input.trim()
    if (!content || isSending) return
    onSend(content)
    setInput('')
  }

  const hasMessages = conversation && conversation.messages.length > 0
  const isEmpty = !hasMessages && !pendingContent

  return (
    <main className="flex-1 flex flex-col overflow-hidden bg-slate-50">

      {/* Thread */}
      <div className="flex-1 overflow-y-auto px-8 py-8">
        {isEmpty ? (
          <div className="h-full flex flex-col items-center justify-center text-center select-none">
            <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center mb-4">
              <span className="text-slate-400 text-base">✦</span>
            </div>

            {!conversation ? (
              <>
                <p className="text-sm font-medium text-slate-700 mb-1">
                  Seleccioná o iniciá una conversación
                </p>
                <p className="text-xs text-slate-400 max-w-xs leading-relaxed">
                  Tus conversaciones se guardan automáticamente. Podés retomar cualquiera desde el panel izquierdo.
                </p>
              </>
            ) : (
              <>
                <p className="text-sm font-medium text-slate-700 mb-1">
                  Comenzá haciendo una pregunta
                </p>
                <p className="text-xs text-slate-400 max-w-xs leading-relaxed">
                  El sistema buscará en los documentos disponibles y responderá con evidencia.
                  Asegurate de haber subido documentos antes de consultar.
                </p>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-6 max-w-3xl mx-auto">
            {conversation?.messages.map(msg => (
              <ChatMessage key={msg.id} msg={msg} />
            ))}

            {/* Optimistic user message + assistant loading — inline in thread */}
            {pendingContent && (
              <>
                <div className="flex justify-end">
                  <div className="max-w-xl bg-slate-900 text-white rounded-2xl rounded-tr-sm px-5 py-3.5">
                    <p className="text-sm leading-relaxed">{pendingContent}</p>
                  </div>
                </div>

                <div className="flex justify-start">
                  <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm shadow-sm px-5 py-3.5">
                    <div className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:0ms]" />
                      <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:150ms]" />
                      <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:300ms]" />
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input bar */}
      <div className="shrink-0 bg-white border-t border-slate-100 px-8 py-4">
        {sendError && (
          <p className="text-[11px] text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2 mb-3">
            {sendError}
          </p>
        )}
        <div className="flex gap-3 max-w-3xl mx-auto">
          <input
            data-testid="message-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            placeholder="Hacé una pregunta sobre tus documentos…"
            disabled={isSending}
            className="flex-1 px-4 py-3 border border-slate-200 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-200 disabled:opacity-60 transition"
          />
          <button
            data-testid="send-btn"
            onClick={handleSubmit}
            disabled={!input.trim() || isSending}
            className="px-5 py-3 bg-slate-900 text-white text-xs font-semibold rounded-xl hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
          >
            {isSending ? 'Consultando…' : 'Consultar'}
          </button>
        </div>
      </div>

    </main>
  )
}
