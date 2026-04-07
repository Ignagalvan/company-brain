'use client'

import Link from 'next/link'
import { Conversation } from '../types'

interface SidebarProps {
  conversations: Conversation[]
  activeConvId: string | null
  onNewConversation: () => void
  onSelectConversation: (id: string) => void
  onDeleteConversation: (id: string) => void
  mobileOpen?: boolean
  onMobileClose?: () => void
}

export function Sidebar({
  conversations,
  activeConvId,
  onNewConversation,
  onSelectConversation,
  onDeleteConversation,
  mobileOpen = false,
  onMobileClose,
}: SidebarProps) {
  const sidebarContent = (
    <>
      <div className="px-4 pt-5 pb-4 border-b border-slate-100">
        <button
          data-testid="new-conversation-btn"
          onClick={() => {
            onNewConversation()
            onMobileClose?.()
          }}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-slate-900 text-white text-sm font-semibold rounded-xl hover:bg-slate-700 active:bg-slate-800 transition-colors"
        >
          <span className="text-base leading-none">+</span>
          Nueva conversación
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {conversations.length === 0 ? (
          <div className="px-5 py-8">
            <p className="text-sm font-medium text-slate-500 mb-1.5">Sin conversaciones</p>
            <p className="text-xs text-slate-400 leading-relaxed">
              Iniciá una nueva conversación para empezar. Documents ahora vive en una pantalla separada para que el chat sea más claro.
            </p>
          </div>
        ) : (
          <ul className="py-2">
            {conversations.map(conv => {
              const isActive = conv.id === activeConvId
              return (
                <li
                  key={conv.id}
                  data-testid="conversation-item"
                  className="group flex items-stretch border-l-2 transition-colors"
                  style={{ borderLeftColor: isActive ? '#0f172a' : 'transparent' }}
                >
                  <button
                    onClick={() => {
                      onSelectConversation(conv.id)
                      onMobileClose?.()
                    }}
                    className={[
                      'flex-1 min-w-0 text-left px-4 py-3.5 flex items-start gap-2.5 transition-colors',
                      isActive ? 'bg-slate-100' : 'hover:bg-slate-50',
                    ].join(' ')}
                  >
                    <span className="mt-0.5 text-slate-400 text-xs shrink-0">◈</span>
                    <span
                      data-testid="conversation-title"
                      className={[
                        'text-sm truncate leading-snug',
                        isActive ? 'font-semibold text-slate-900' : 'font-normal text-slate-600',
                      ].join(' ')}
                    >
                      {conv.title}
                    </span>
                  </button>
                  <button
                    data-testid="delete-conversation-btn"
                    onClick={() => onDeleteConversation(conv.id)}
                    title="Eliminar conversación"
                    className={[
                      'shrink-0 px-3 text-sm transition-all',
                      'opacity-0 group-hover:opacity-100',
                      'text-slate-400 hover:text-red-500',
                      isActive ? 'bg-slate-100' : 'hover:bg-slate-50',
                    ].join(' ')}
                  >
                    ×
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <div className="border-t border-slate-100 bg-slate-50/60 px-4 py-4">
        <Link
          href="/documents"
          onClick={() => onMobileClose?.()}
          className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 hover:border-slate-300 transition-colors"
        >
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">Documents</p>
            <p className="mt-1 text-sm font-medium text-slate-800">Ver documentos</p>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">
              Revisá uso, cobertura y oportunidades de mejora de tu base de conocimiento.
            </p>
          </div>
          <span className="shrink-0 text-slate-400 text-lg leading-none">→</span>
        </Link>
      </div>
    </>
  )

  return (
    <>
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 top-14 z-20 bg-black/20"
          onClick={onMobileClose}
        />
      )}

      <aside
        className={[
          'flex-col overflow-hidden bg-white border-r border-slate-100',
          'md:flex md:relative md:w-64 md:shrink-0',
          'md:top-auto md:bottom-auto md:z-auto md:shadow-none md:translate-x-0',
          mobileOpen
            ? 'flex fixed left-0 top-14 bottom-0 z-30 w-72 shadow-xl'
            : 'hidden',
        ].join(' ')}
      >
        {sidebarContent}
      </aside>
    </>
  )
}
