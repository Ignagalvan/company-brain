'use client'

import { useEffect, useMemo, useState } from 'react'
import { AppShell } from '../../app/components/AppShell'
import { DocumentListRow, DocumentsNav, DocumentsSectionHeader } from '../_components'
import { API_URL, cleanFilename, DocumentsOverview, ORG_ID } from '../_lib'

type FilterKey = 'all' | 'helping' | 'unused' | 'related'

export default function DocumentsListPage() {
  const [data, setData] = useState<DocumentsOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<FilterKey>('all')
  const [deletingId, setDeletingId] = useState<string | null>(null)

  async function loadOverview() {
    setLoading(true)
    setError(false)
    try {
      const res = await fetch(`${API_URL}/documents/overview`, { headers: { 'X-Organization-Id': ORG_ID } })
      if (!res.ok) throw new Error()
      setData(await res.json())
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadOverview()
  }, [])

  async function handleUpload(file: File) {
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      await fetch(`${API_URL}/documents/upload`, {
        method: 'POST',
        headers: { 'X-Organization-Id': ORG_ID },
        body: formData,
      })
      await loadOverview()
    } finally {
      setUploading(false)
    }
  }

  async function handleDelete(documentId: string) {
    setDeletingId(documentId)
    try {
      await fetch(`${API_URL}/documents/${documentId}`, {
        method: 'DELETE',
        headers: { 'X-Organization-Id': ORG_ID },
      })
      await loadOverview()
    } finally {
      setDeletingId(null)
    }
  }

  const filteredDocuments = useMemo(() => {
    const documents = data?.documents ?? []
    return documents
      .filter(doc => {
        const haystack = `${cleanFilename(doc.filename)} ${doc.related_gap_topics.join(' ')}`.toLowerCase()
        return haystack.includes(query.trim().toLowerCase())
      })
      .filter(doc => {
        if (filter === 'helping') return doc.is_helping
        if (filter === 'unused') return doc.usage_count === 0
        if (filter === 'related') return doc.related_active_gaps_count > 0
        return true
      })
  }, [data, filter, query])

  const filters: { key: FilterKey; label: string }[] = [
    { key: 'all', label: 'Todos' },
    { key: 'helping', label: 'Aportan valor' },
    { key: 'unused', label: 'Sin uso' },
    { key: 'related', label: 'Relacionados con gaps' },
  ]

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto bg-slate-50">
        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
          <DocumentsSectionHeader
            title="All Documents"
            subtitle="Gestioná toda la base documental con una lista compacta, clara y fácil de recorrer en desktop y mobile."
            onUpload={handleUpload}
            uploading={uploading}
            primaryHref="/documents"
            primaryLabel="Volver al overview"
          />
          <DocumentsNav />

          <section className="mb-5 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 md:flex-row md:items-center md:justify-between">
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Buscar por nombre o gap relacionado"
              className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 text-[14px] text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200 md:max-w-sm"
            />
            <div className="flex flex-wrap gap-2">
              {filters.map(item => (
                <button
                  key={item.key}
                  onClick={() => setFilter(item.key)}
                  className={[
                    'rounded-full px-3 py-1.5 text-[12px] font-medium transition-colors',
                    filter === item.key
                      ? 'bg-slate-900 text-white'
                      : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                  ].join(' ')}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </section>

          {loading && (
            <div className="space-y-3">
              {[0, 1, 2, 3].map(i => (
                <div key={i} className="h-24 animate-pulse rounded-2xl border border-slate-200 bg-white" />
              ))}
            </div>
          )}

          {error && !loading && (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700">
              No se pudo cargar la lista de documentos.
            </div>
          )}

          {!loading && !error && (
            <section className="space-y-3">
              {filteredDocuments.length === 0 ? (
                <div className="rounded-2xl border border-slate-200 bg-white px-5 py-10 text-center text-[14px] text-slate-400">
                  No hay documentos para este filtro.
                </div>
              ) : (
                filteredDocuments.map(doc => (
                  <DocumentListRow
                    key={doc.id}
                    doc={doc}
                    onDelete={handleDelete}
                    deleting={deletingId === doc.id}
                  />
                ))
              )}
            </section>
          )}
        </main>
      </div>
    </AppShell>
  )
}
