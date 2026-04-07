'use client'

import { useEffect, useState } from 'react'
import { AppShell } from '../app/components/AppShell'
import { DocumentsNav, DocumentsSectionHeader, InsightList, MetricCard } from './_components'
import { API_URL, DocumentsOverview, ORG_ID, relativeTime } from './_lib'

export default function DocumentsOverviewPage() {
  const [data, setData] = useState<DocumentsOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')

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
    setUploadMessage('')
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch(`${API_URL}/documents/upload`, {
        method: 'POST',
        headers: { 'X-Organization-Id': ORG_ID },
        body: formData,
      })
      if (!res.ok) throw new Error()
      setUploadMessage(`"${file.name}" se subió correctamente.`)
      await loadOverview()
    } catch {
      setUploadMessage('No se pudo subir el documento.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto bg-slate-50">
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
          <DocumentsSectionHeader
            title="Documents Overview"
            subtitle="Entendé el estado general de tu base documental y decidí rápido qué revisar primero."
            onUpload={handleUpload}
            uploading={uploading}
            primaryHref="/documents/list"
            primaryLabel="Ver todos los documentos"
          />
          <DocumentsNav />

          {uploadMessage && (
            <div className="mb-5 rounded-xl border border-slate-200 bg-white px-4 py-3 text-[13px] text-slate-600">
              {uploadMessage}
            </div>
          )}

          {loading && (
            <div className="space-y-3">
              {[0, 1, 2].map(i => (
                <div key={i} className="h-24 animate-pulse rounded-2xl border border-slate-200 bg-white" />
              ))}
            </div>
          )}

          {error && !loading && (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700">
              No se pudo cargar Documents desde el backend.
            </div>
          )}

          {!loading && !error && data && (
            <>
              <section className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                  label="Documentos totales"
                  value={String(data.insights.total_documents)}
                  sub={`${data.insights.processed_documents} procesados`}
                />
                <MetricCard
                  label="Aportan valor"
                  value={String(data.insights.documents_helping_count)}
                  sub="Citados en respuestas reales"
                />
                <MetricCard
                  label="Sin uso"
                  value={String(data.insights.unused_documents_count)}
                  sub="Todavía no usados en respuestas"
                />
                <MetricCard
                  label="Con relación a gaps"
                  value={String(data.insights.documents_related_to_gaps_count)}
                  sub="Podrían ayudar a cerrar gaps activos"
                />
              </section>

              <section className="grid gap-4 xl:grid-cols-3">
                <InsightList
                  title="Más usados"
                  subtitle="Qué documentos sí están sosteniendo respuestas."
                  items={data.insights.most_used}
                  renderMeta={item => `Se usó en ${item.usage_count} respuesta${item.usage_count !== 1 ? 's' : ''}. Último uso: ${relativeTime(item.last_used_at)}.`}
                />
                <InsightList
                  title="Sin uso"
                  subtitle="Qué contenido todavía no aporta valor visible."
                  items={data.insights.never_used}
                  renderMeta={item => `Todavía no fue usado en respuestas. Subido ${relativeTime(item.created_at)}.`}
                />
                <InsightList
                  title="Podrían ayudar con gaps"
                  subtitle="Qué documentos aparecen vinculados a gaps activos."
                  items={data.insights.could_resolve_gaps}
                  renderMeta={item => `Podría ayudar a resolver ${item.related_active_gaps_count} gap${item.related_active_gaps_count !== 1 ? 's' : ''}.`}
                />
              </section>
            </>
          )}
        </main>
      </div>
    </AppShell>
  )
}
