'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Sidebar } from './components/Sidebar'
import { ChatArea } from './components/ChatArea'
import { Conversation, Message, UploadedDoc } from './types'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ORG_ID = process.env.NEXT_PUBLIC_ORG_ID ?? '00000000-0000-0000-0000-000000000001'

const HEADERS = {
  'Content-Type': 'application/json',
  'X-Organization-Id': ORG_ID,
}

export default function AppPage() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDoc[]>([])
  const [pendingContent, setPendingContent] = useState('')
  const [sendError, setSendError] = useState('')

  const activeConv = conversations.find(c => c.id === activeConvId) ?? null

  // Load conversations on mount
  useEffect(() => {
    fetch(`${API_URL}/conversations`, { headers: HEADERS })
      .then(r => r.ok ? r.json() : [])
      .then((data: Omit<Conversation, 'messages'>[]) => {
        setConversations(data.map(c => ({ ...c, messages: [] })))
      })
      .catch(() => {})
  }, [])

  // Load documents on mount
  useEffect(() => {
    fetch(`${API_URL}/documents`, { headers: HEADERS })
      .then(r => r.ok ? r.json() : [])
      .then((data: { id: string; filename: string }[]) => {
        setUploadedDocs(data.map(d => ({
          id: d.id,
          filename: d.filename.replace(/^[0-9a-f-]{36}_/i, ''),
        })))
      })
      .catch(() => {})
  }, [])

  function handleNewConversation() {
    setActiveConvId(null)
    setSendError('')
  }

  async function handleSelectConversation(id: string) {
    setActiveConvId(id)
    setSendError('')

    try {
      const res = await fetch(`${API_URL}/conversations/${id}`, { headers: HEADERS })
      if (!res.ok) return
      const data: Conversation = await res.json()
      setConversations(prev => prev.map(c => c.id === id ? data : c))
    } catch {}
  }

  async function handleDeleteConversation(id: string) {
    try {
      await fetch(`${API_URL}/conversations/${id}`, { method: 'DELETE', headers: HEADERS })
    } catch {}
    setConversations(prev => prev.filter(c => c.id !== id))
    if (activeConvId === id) setActiveConvId(null)
  }

  function handleDocUploaded(doc: UploadedDoc) {
    setUploadedDocs(prev => [...prev, doc])
  }

  async function handleDeleteDoc(id: string) {
    try {
      await fetch(`${API_URL}/documents/${id}`, { method: 'DELETE', headers: HEADERS })
    } catch {}
    setUploadedDocs(prev => prev.filter(d => d.id !== id))
  }

  async function handleSend(content: string) {
    setPendingContent(content)
    setSendError('')

    try {
      const res = await fetch(`${API_URL}/conversations/messages`, {
        method: 'POST',
        headers: HEADERS,
        body: JSON.stringify({
          conversation_id: activeConvId ?? null,
          content,
        }),
      })

      if (!res.ok) {
        setSendError(res.status === 502
          ? 'No se pudo generar una respuesta. Intentá de nuevo.'
          : 'Error al enviar el mensaje.')
        return
      }

      const assistantMsg: Message = await res.json()
      const convId = assistantMsg.conversation_id

      // Fetch full conversation to get consistent state (user + assistant messages)
      const convRes = await fetch(`${API_URL}/conversations/${convId}`, { headers: HEADERS })
      const fullConv: Conversation | null = convRes.ok ? await convRes.json() : null

      setConversations(prev => {
        const exists = prev.find(c => c.id === convId)

        if (!exists) {
          const newConv: Conversation = fullConv ?? {
            id: convId,
            title: content.trim().slice(0, 60) || 'Nueva conversación',
            updated_at: assistantMsg.created_at,
            messages: [assistantMsg],
          }
          return [newConv, ...prev]
        }

        const updated = fullConv ?? prev.find(c => c.id === convId)!
        return [updated, ...prev.filter(c => c.id !== convId)]
      })

      setActiveConvId(convId)
    } catch {
      setSendError('No se pudo conectar con el backend.')
    } finally {
      setPendingContent('')
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
          onDeleteDoc={handleDeleteDoc}
        />
        <ChatArea
          conversation={activeConv}
          pendingContent={pendingContent}
          sendError={sendError}
          onSend={handleSend}
        />
      </div>

    </div>
  )
}
