'use client'

import { useCallback, useRef, useState } from 'react'
import { Conversation, UploadedDoc } from '../types'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ORG_ID = process.env.NEXT_PUBLIC_ORG_ID ?? '00000000-0000-0000-0000-000000000001'

function cleanFilename(raw: string): string {
  const match = raw.match(/^[0-9a-f-]{36}_(.+)$/i)
  return match ? match[1] : raw
}

interface SidebarProps {
  conversations: Conversation[]
  activeConvId: string | null
  uploadedDocs: UploadedDoc[]
  onNewConversation: () => void
  onSelectConversation: (id: string) => void
  onDeleteConversation: (id: string) => void
  onDocUploaded: (doc: UploadedDoc) => void
  onDeleteDoc: (id: string) => void
}

export function Sidebar({
  conversations,
  activeConvId,
  uploadedDocs,
  onNewConversation,
  onSelectConversation,
  onDeleteConversation,
  onDocUploaded,
  onDeleteDoc,
}: SidebarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const dragCounterRef = useRef(0)

  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [uploadMessage, setUploadMessage] = useState('')

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    dragCounterRef.current++
    setIsDragging(true)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    dragCounterRef.current--
    if (dragCounterRef.current === 0) setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    dragCounterRef.current = 0
    setIsDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped?.type === 'application/pdf') {
      setFile(dropped)
      setUploadStatus('idle')
    }
  }, [])

  function clearFile() {
    setFile(null)
    setUploadStatus('idle')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setUploadStatus('idle')
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch(`${API_URL}/documents/upload`, {
        method: 'POST',
        headers: { 'X-Organization-Id': ORG_ID },
        body: formData,
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const clean = cleanFilename(data.filename)
      setUploadStatus('success')
      setUploadMessage(`"${clean}" procesado correctamente.`)
      onDocUploaded({ id: data.id, filename: clean })
      clearFile()
    } catch {
      setUploadStatus('error')
      setUploadMessage('Error al subir. Verificá que el backend esté activo.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <aside className="w-72 shrink-0 bg-white border-r border-slate-100 flex flex-col overflow-hidden">

      {/* New conversation */}
      <div className="px-4 pt-5 pb-4 border-b border-slate-100">
        <button
          data-testid="new-conversation-btn"
          onClick={onNewConversation}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-slate-900 text-white text-sm font-semibold rounded-xl hover:bg-slate-700 transition-colors"
        >
          <span className="text-base leading-none">+</span>
          Nueva conversación
        </button>
      </div>

      {/* Conversations list */}
      <div className="flex-1 overflow-y-auto">
        {conversations.length === 0 ? (
          <div className="px-5 py-8">
            <p className="text-sm font-medium text-slate-500 mb-1.5">Sin conversaciones</p>
            <p className="text-xs text-slate-400 leading-relaxed">
              Iniciá una nueva conversación para comenzar a consultar tus documentos.
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
                    onClick={() => onSelectConversation(conv.id)}
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

      {/* Documents + Upload */}
      <div className="border-t border-slate-100 bg-slate-50/60 px-4 py-5 space-y-5">

        {/* Documents list */}
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-2.5">
            Documentos
            {uploadedDocs.length > 0 && (
              <span className="ml-1 font-normal text-slate-400">({uploadedDocs.length})</span>
            )}
          </p>
          {uploadedDocs.length === 0 ? (
            <p className="text-xs text-slate-400 leading-relaxed">
              Ningún documento cargado.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {uploadedDocs.map(doc => (
                <li key={doc.id} data-testid="document-item" className="group flex items-center gap-2 px-3 py-2 bg-white rounded-lg border border-slate-100">
                  <span className="shrink-0 text-xs text-emerald-500 font-bold">✓</span>
                  <span data-testid="document-name" className="text-xs text-slate-700 truncate flex-1">{doc.filename}</span>
                  <button
                    data-testid="delete-doc-btn"
                    onClick={() => onDeleteDoc(doc.id)}
                    title="Eliminar documento"
                    className="shrink-0 opacity-0 group-hover:opacity-100 text-sm text-slate-400 hover:text-red-500 transition-all"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Upload zone */}
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2.5">
            Subir PDF
          </p>

          <input
            ref={fileInputRef}
            data-testid="file-input"
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={(e) => {
              const selected = e.target.files?.[0]
              if (selected) {
                setFile(selected)
                setUploadStatus('idle')
              }
            }}
          />

          <div
            onClick={() => fileInputRef.current?.click()}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={[
              'border-2 border-dashed rounded-xl px-3 py-5 text-center cursor-pointer transition-colors select-none',
              isDragging
                ? 'border-slate-400 bg-slate-100'
                : file
                  ? 'border-slate-300 bg-slate-50'
                  : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50',
            ].join(' ')}
          >
            {file ? (
              <div>
                <p className="text-xs font-medium text-slate-700 truncate">{file.name}</p>
                <p className="text-[11px] text-slate-400 mt-0.5">{(file.size / 1024).toFixed(0)} KB</p>
              </div>
            ) : (
              <p className="text-xs text-slate-500">
                {isDragging ? 'Soltá el archivo' : 'Arrastrá o hacé clic para subir un PDF'}
              </p>
            )}
          </div>

          <div className="flex items-center justify-between mt-2.5">
            {file ? (
              <button onClick={clearFile} className="text-xs text-slate-400 hover:text-slate-600 transition-colors">
                Cambiar
              </button>
            ) : <span />}
            <button
              data-testid="upload-btn"
              onClick={handleUpload}
              disabled={!file || uploading}
              className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-lg hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {uploading ? 'Procesando…' : 'Subir'}
            </button>
          </div>

          {uploadStatus === 'success' && (
            <p className="mt-2.5 text-xs text-emerald-700 bg-emerald-50 border border-emerald-100 px-3 py-2 rounded-lg">
              ✓ {uploadMessage}
            </p>
          )}
          {uploadStatus === 'error' && (
            <p className="mt-2.5 text-xs text-red-600 bg-red-50 border border-red-100 px-3 py-2 rounded-lg">
              {uploadMessage}
            </p>
          )}
        </div>

      </div>
    </aside>
  )
}
