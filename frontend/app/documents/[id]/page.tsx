'use client'

import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { AppShell } from '../../app/components/AppShell'
import { DocumentDetailSummary, DocumentsNav, MetricCard, ValueChip } from '../_components'
import { API_URL, DocumentDetail, ORG_ID, relativeTime } from '../_lib'

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const [doc, setDoc] = useState<DocumentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    async function loadDetail() {
      setLoading(true)
      setError(false)
      try {
        const res = await fetch(`${API_URL}/documents/${params.id}/detail`, {
          headers: { 'X-Organization-Id': ORG_ID },
        })
        if (!res.ok) throw new Error()
        setDoc(await res.json())
      } catch {
        setError(true)
      } finally {
        setLoading(false)
      }
    }

    if (params.id) loadDetail()
  }, [params.id])

  async function handleDelete() {
    if (!doc) return
    setDeleting(true)
    try {
      await fetch(`${API_URL}/documents/${doc.id}`, {
        method: 'DELETE',
        headers: { 'X-Organization-Id': ORG_ID },
      })
      router.push('/documents/list')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto bg-slate-50">
        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
          <div className="mb-4">
            <Link href="/documents/list" className="text-[13px] font-medium text-slate-500 hover:text-slate-800">
              ← Volver a Documents List
            </Link>
          </div>
          <DocumentsNav />

          {loading && (
            <div className="space-y-3">
              {[0, 1, 2].map(i => (
                <div key={i} className="h-24 animate-pulse rounded-2xl border border-slate-200 bg-white" />
              ))}
            </div>
          )}

          {error && !loading && (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700">
              No se pudo cargar el detalle del documento.
            </div>
          )}

          {!loading && !error && doc && (
            <>
              <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-5">
                <DocumentDetailSummary doc={doc} />
                <div className="mt-4 flex flex-wrap gap-2">
                  <Link
                    href="/documents/list"
                    className="rounded-lg border border-slate-200 px-3 py-2 text-[13px] font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Ver todos los documentos
                  </Link>
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="rounded-lg border border-red-200 px-3 py-2 text-[13px] font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                  >
                    {deleting ? 'Eliminando…' : 'Eliminar documento'}
                  </button>
                </div>
              </section>

              <section className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard label="Chunks" value={String(doc.chunks_count)} sub="Tamaño operativo del documento" />
                <MetricCard label="Usos" value={String(doc.usage_count)} sub="Veces citado en respuestas" />
                <MetricCard label="Último uso" value={relativeTime(doc.last_used_at)} sub="Última vez que ayudó a responder" />
                <MetricCard label="Gaps relacionados" value={String(doc.related_active_gaps_count)} sub="Señal actual contra gaps activos" />
              </section>

              <section className="mb-6 grid gap-4 xl:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Aporte actual</p>
                  <p className="mt-2 text-[14px] leading-relaxed text-slate-700">
                    {doc.usage_count > 0
                      ? `Este documento sí está ayudando: fue usado en ${doc.usage_count} respuesta${doc.usage_count !== 1 ? 's' : ''}.`
                      : 'Este documento todavía no aportó valor visible en respuestas.'}
                  </p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Relación con gaps</p>
                  <p className="mt-2 text-[14px] leading-relaxed text-slate-700">
                    {doc.related_active_gaps_count > 0
                      ? `Aparece relacionado con ${doc.related_active_gaps_count} gap${doc.related_active_gaps_count !== 1 ? 's' : ''} activo${doc.related_active_gaps_count !== 1 ? 's' : ''}.`
                      : 'No aparece vinculado a gaps activos con la señal disponible hoy.'}
                  </p>
                  {doc.related_gap_topics.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {doc.related_gap_topics.map(topic => (
                        <ValueChip key={topic} label={topic} tone="warn" />
                      ))}
                    </div>
                  )}
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Estado operativo</p>
                  <p className="mt-2 text-[14px] leading-relaxed text-slate-700">
                    {doc.chunks_count > 0
                      ? `Ya está listo para retrieval con ${doc.chunks_count} chunks procesados.`
                      : 'Todavía no muestra chunks procesados, así que su aporte puede ser limitado.'}
                  </p>
                </div>
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white">
                <div className="border-b border-slate-100 px-5 py-4">
                  <h2 className="text-[16px] font-semibold text-slate-900">Preview del contenido extraído</h2>
                  <p className="mt-1 text-[13px] text-slate-500">
                    Este preview permite revisar si el contenido cargado realmente es útil y legible.
                  </p>
                </div>
                <div className="px-5 py-4">
                  {doc.extracted_text ? (
                    <pre className="whitespace-pre-wrap text-[13px] leading-relaxed text-slate-700">{doc.extracted_text}</pre>
                  ) : (
                    <p className="text-[13px] text-slate-500">
                      Este documento no tiene texto extraído disponible para preview.
                    </p>
                  )}
                </div>
              </section>
            </>
          )}
        </main>
      </div>
    </AppShell>
  )
}
