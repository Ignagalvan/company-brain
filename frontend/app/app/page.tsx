'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Sidebar } from './components/Sidebar'
import { ChatArea } from './components/ChatArea'
import { Conversation, Message, UploadedDoc } from './types'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ORG_ID = process.env.NEXT_PUBLIC_ORG_ID ?? '00000000-0000-0000-0000-000000000001'

function newConversation(): Conversation {
  return { id: Date.now().toString(), title: 'Nueva conversación', messages: [] }
}

export default function AppPage() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDoc[]>([])
  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState('')

  const activeConv = conversations.find(c => c.id === activeConvId) ?? null

  // Don't create the conversation yet — it's created in handleAsk on first message.
  function handleNewConversation() {
    setActiveConvId(null)
    setAskError('')
  }

  function handleSelectConversation(id: string) {
    setActiveConvId(id)
    setAskError('')
  }

  function handleDeleteConversation(id: string) {
    setConversations(prev => prev.filter(c => c.id !== id))
    if (activeConvId === id) setActiveConvId(null)
  }

  function handleDocUploaded(doc: UploadedDoc) {
    setUploadedDocs(prev => [...prev, doc])
  }

  async function handleAsk(query: string) {
    // Ensure active conversation
    let convId = activeConvId
    if (!convId) {
      const conv = newConversation()
      setConversations(prev => [conv, ...prev])
      convId = conv.id
      setActiveConvId(convId)
    }

    const userMsg: Message = { id: Date.now(), type: 'user', content: query }

    // Add user message + update title on first message
    setConversations(prev => prev.map(c => {
      if (c.id !== convId) return c
      return {
        ...c,
        title: c.messages.length === 0 ? query.slice(0, 45) : c.title,
        messages: [...c.messages, userMsg],
      }
    }))

    setAsking(true)
    setAskError('')

    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Organization-Id': ORG_ID,
        },
        body: JSON.stringify({ query, top_k: 5 }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()

      const sysMsg: Message = {
        id: Date.now() + 1,
        type: 'system',
        content: data.answer,
        sources: data.sources,
      }

      setConversations(prev => prev.map(c => {
        if (c.id !== convId) return c
        return { ...c, messages: [...c.messages, sysMsg] }
      }))
    } catch {
      setAskError('No se pudo obtener una respuesta. Verificá que el backend esté activo.')
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="h-screen bg-slate-50 font-sans flex flex-col overflow-hidden">

      {/* Header */}
      <header className="bg-white border-b border-slate-100 shrink-0">
        <div className="h-12 px-6 flex items-center justify-between">
          <Link href="/" className="text-sm font-semibold text-slate-900 hover:text-slate-500 transition-colors">
            Company Brain
          </Link>
          <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
            Demo
          </span>
        </div>
      </header>

      {/* Workspace */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          conversations={conversations}
          activeConvId={activeConvId}
          uploadedDocs={uploadedDocs}
          onNewConversation={handleNewConversation}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
          onDocUploaded={handleDocUploaded}
        />
        <ChatArea
          conversation={activeConv}
          asking={asking}
          askError={askError}
          onAsk={handleAsk}
        />
      </div>

    </div>
  )
}
