'use client'

import { useEffect, useRef, useState } from 'react'
import { Conversation } from '../types'
import { ChatMessage } from './ChatMessage'

function IconPanelLeft() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <line x1="9" y1="3" x2="9" y2="21" />
    </svg>
  )
}

function IconSend() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}

interface ChatAreaProps {
  conversation: Conversation | null
  pendingContent: string
  sendError: string
  onSend: (content: string) => void
  onToggleSidebar?: () => void
}

export function ChatArea({ conversation, pendingContent, sendError, onSend, onToggleSidebar }: ChatAreaProps) {
  const [input, setInput] = useState('')
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const isSending = pendingContent !== ''

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation?.messages.length, pendingContent])

  function handleSubmit() {
    const content = input.trim()
    if (!content || isSending) return
    onSend(content)
    setInput('')
    // Reset textarea height
    if (inputRef.current) inputRef.current.style.height = 'auto'
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value)
    // Auto-resize textarea
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  const hasMessages = conversation && conversation.messages.length > 0
  const isEmpty = !hasMessages && !pendingContent

  return (
    <main className="flex-1 flex flex-col overflow-hidden bg-slate-50">

      {/* Mobile sub-header: conversation panel toggle */}
      <div className="md:hidden shrink-0 flex items-center gap-3 px-4 h-12 bg-white border-b border-slate-100">
        <button
          onClick={onToggleSidebar}
          className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-800 active:text-slate-900 transition-colors"
          aria-label="Ver conversaciones"
        >
          <IconPanelLeft />
          <span>Conversaciones</span>
        </button>
        {conversation && (
          <>
            <span className="text-slate-300">/</span>
            <span className="text-sm text-slate-400 truncate">{conversation.title}</span>
          </>
        )}
      </div>

      {/* Thread */}
      <div className="flex-1 overflow-y-auto px-4 py-8 sm:px-6 lg:px-12">
        {isEmpty ? (
          <div className="h-full flex flex-col items-center justify-center text-center select-none px-6">
            <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center mb-5">
              <span className="text-slate-400 text-lg">✦</span>
            </div>

            {!conversation ? (
              <>
                <p className="text-base font-semibold text-slate-700 mb-2">
                  Seleccioná o iniciá una conversación
                </p>
                <p className="text-sm text-slate-400 max-w-xs leading-relaxed">
                  Tus conversaciones se guardan automáticamente. Podés retomar cualquiera desde el panel izquierdo.
                </p>
              </>
            ) : (
              <>
                <p className="text-base font-semibold text-slate-700 mb-2">
                  Comenzá haciendo una pregunta
                </p>
                <p className="text-sm text-slate-400 max-w-xs leading-relaxed">
                  El sistema buscará en los documentos disponibles y responderá con evidencia.
                  Asegurate de haber subido documentos antes de consultar.
                </p>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-8 max-w-3xl mx-auto">
            {conversation?.messages.map(msg => (
              <ChatMessage key={msg.id} msg={msg} />
            ))}

            {/* Optimistic user message + assistant loading */}
            {pendingContent && (
              <>
                <div className="flex justify-end">
                  <div className="max-w-xl bg-slate-900 text-white rounded-2xl rounded-tr-sm px-5 py-4">
                    <p className="text-[15px] leading-relaxed">{pendingContent}</p>
                  </div>
                </div>

                <div className="flex justify-start">
                  <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm shadow-sm px-6 py-4">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:0ms]" />
                      <span className="w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:150ms]" />
                      <span className="w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:300ms]" />
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
      <div className="shrink-0 bg-white border-t border-slate-100 px-4 py-4 sm:px-6 lg:px-12">
        {sendError && (
          <p className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2 mb-3 max-w-3xl mx-auto">
            {sendError}
          </p>
        )}
        <div className="flex gap-3 max-w-3xl mx-auto items-end">
          <textarea
            ref={inputRef}
            data-testid="message-input"
            rows={1}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Hacé una pregunta sobre tus documentos…"
            disabled={isSending}
            className="flex-1 px-4 py-3 border border-slate-200 rounded-xl text-[15px] text-slate-900 placeholder:text-slate-400 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-200 focus:bg-white disabled:opacity-60 transition resize-none leading-relaxed overflow-hidden"
            style={{ minHeight: '48px' }}
          />
          <button
            data-testid="send-btn"
            onClick={handleSubmit}
            disabled={!input.trim() || isSending}
            className="shrink-0 h-12 px-5 bg-slate-900 text-white text-sm font-semibold rounded-xl hover:bg-slate-700 active:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            <IconSend />
            <span className="hidden sm:inline">{isSending ? 'Consultando…' : 'Consultar'}</span>
          </button>
        </div>
        <p className="mt-2 text-[11px] text-slate-400 text-center max-w-3xl mx-auto">
          Enter para enviar · Shift+Enter para nueva línea
        </p>
      </div>

    </main>
  )
}
