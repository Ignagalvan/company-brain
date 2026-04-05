'use client'

import { useEffect, useRef, useState } from 'react'
import { AppShell } from './components/AppShell'
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
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)

  // AbortController for the in-flight send request.
  // Cancels the previous request when the user switches conversations or sends a new one.
  const sendAbortRef = useRef<AbortController | null>(null)

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
    // Cancel any in-flight send and clear pending state immediately
    sendAbortRef.current?.abort()
    sendAbortRef.current = null
    setActiveConvId(null)
    setPendingContent('')
    setSendError('')
  }

  async function handleSelectConversation(id: string) {
    // Cancel any in-flight send and clear pending state immediately
    sendAbortRef.current?.abort()
    sendAbortRef.current = null
    setPendingContent('')
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
    if (activeConvId === id) {
      sendAbortRef.current?.abort()
      sendAbortRef.current = null
      setPendingContent('')
    }
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
    // Abort any previous in-flight request (e.g. rapid re-sends)
    sendAbortRef.current?.abort()
    const controller = new AbortController()
    sendAbortRef.current = controller

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
        signal: controller.signal,
      })

      // Request was aborted (user switched conversations) — discard result silently
      if (controller.signal.aborted) return

      if (!res.ok) {
        setSendError(res.status === 502
          ? 'No se pudo generar una respuesta. Intentá de nuevo.'
          : 'Error al enviar el mensaje.')
        return
      }

      const assistantMsg: Message = await res.json()

      // Check again after parsing JSON (async microtask may have yielded)
      if (controller.signal.aborted) return

      const convId = assistantMsg.conversation_id

      // Fetch full conversation for consistent user+assistant state
      const convRes = await fetch(`${API_URL}/conversations/${convId}`, {
        headers: HEADERS,
        signal: controller.signal,
      })
      const fullConv: Conversation | null = convRes.ok ? await convRes.json() : null

      if (controller.signal.aborted) return

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
    } catch (e) {
      // AbortError is expected when the user switches conversations — ignore it
      if (e instanceof Error && e.name === 'AbortError') return
      setSendError('No se pudo conectar con el backend.')
    } finally {
      // Always clear the loading indicator
      setPendingContent('')
    }
  }

  return (
    <AppShell>
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
          mobileOpen={mobileSidebarOpen}
          onMobileClose={() => setMobileSidebarOpen(false)}
        />
        <ChatArea
          conversation={activeConv}
          pendingContent={pendingContent}
          sendError={sendError}
          onSend={handleSend}
          onToggleSidebar={() => setMobileSidebarOpen(v => !v)}
        />
      </div>
    </AppShell>
  )
}
