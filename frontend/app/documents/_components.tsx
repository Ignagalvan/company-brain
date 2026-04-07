'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useRef } from 'react'
import { cleanFilename, DocumentItem, formatDate, relativeTime } from './_lib'

export function DocumentsSectionHeader({
  title,
  subtitle,
  onUpload,
  uploading = false,
  primaryHref,
  primaryLabel,
}: {
  title: string
  subtitle: string
  onUpload?: (file: File) => void
  uploading?: boolean
  primaryHref?: string
  primaryLabel?: string
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  return (
    <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">Knowledge Base</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        <p className="mt-2 max-w-2xl text-[14px] leading-relaxed text-slate-500">{subtitle}</p>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        {primaryHref && primaryLabel && (
          <Link
            href={primaryHref}
            className="inline-flex h-11 items-center justify-center rounded-xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            {primaryLabel}
          </Link>
        )}
        {onUpload && (
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={e => {
                const file = e.target.files?.[0]
                if (file) {
                  onUpload(file)
                  e.currentTarget.value = ''
                }
              }}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="h-11 rounded-xl bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50 transition-colors"
            >
              {uploading ? 'Subiendo…' : 'Subir nuevo PDF'}
            </button>
          </>
        )}
      </div>
    </div>
  )
}

export function DocumentsNav() {
  const pathname = usePathname()
  const items = [
    { href: '/documents', label: 'Overview' },
    { href: '/documents/list', label: 'All Documents' },
  ]

  return (
    <div className="mb-5 flex flex-wrap gap-2">
      {items.map(item => {
        const active = pathname === item.href
        return (
          <Link
            key={item.href}
            href={item.href}
            className={[
              'rounded-full px-3 py-1.5 text-[13px] font-medium transition-colors',
              active
                ? 'bg-slate-900 text-white'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50',
            ].join(' ')}
          >
            {item.label}
          </Link>
        )
      })}
    </div>
  )
}

export function MetricCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
      <p className="mt-1 text-[12px] leading-relaxed text-slate-500">{sub}</p>
    </div>
  )
}

export function StatusChip({ state }: { state: 'processed' | 'pending' }) {
  return (
    <span
      className={[
        'inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-medium',
        state === 'processed'
          ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
          : 'bg-amber-50 text-amber-700 border border-amber-100',
      ].join(' ')}
    >
      {state === 'processed' ? 'Procesado' : 'Pendiente'}
    </span>
  )
}

export function ValueChip({ label, tone = 'neutral' }: { label: string; tone?: 'neutral' | 'good' | 'warn' }) {
  return (
    <span
      className={[
        'inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-medium',
        tone === 'good'
          ? 'bg-emerald-50 text-emerald-700'
          : tone === 'warn'
          ? 'bg-amber-50 text-amber-700'
          : 'bg-slate-100 text-slate-600',
      ].join(' ')}
    >
      {label}
    </span>
  )
}

export function InsightList({
  title,
  subtitle,
  items,
  renderMeta,
}: {
  title: string
  subtitle: string
  items: DocumentItem[]
  renderMeta: (item: DocumentItem) => string
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="mb-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{title}</p>
        <p className="mt-1 text-[13px] leading-relaxed text-slate-500">{subtitle}</p>
      </div>
      {items.length === 0 ? (
        <p className="text-[13px] text-slate-400">Todavía no hay señal suficiente.</p>
      ) : (
        <div className="space-y-2.5">
          {items.map(item => (
            <div key={item.id} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-3">
              <p className="text-[13px] font-medium text-slate-900">{cleanFilename(item.filename)}</p>
              <p className="mt-1 text-[12px] text-slate-500 leading-relaxed">{renderMeta(item)}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export function DocumentListRow({
  doc,
  onDelete,
  deleting,
}: {
  doc: DocumentItem
  onDelete: (id: string) => void
  deleting?: boolean
}) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate text-[14px] font-semibold text-slate-900">{cleanFilename(doc.filename)}</p>
          <StatusChip state={doc.processing_state} />
        </div>
        <div className="mt-2 flex flex-wrap gap-2 text-[12px]">
          <ValueChip label={`${doc.chunks_count} chunks`} />
          <ValueChip label={`${doc.usage_count} usos`} tone={doc.is_helping ? 'good' : 'neutral'} />
          <ValueChip label={`Último uso: ${relativeTime(doc.last_used_at)}`} />
          {doc.related_active_gaps_count > 0 && (
            <ValueChip label={`${doc.related_active_gaps_count} gaps`} tone="warn" />
          )}
        </div>
      </div>
      <div className="flex shrink-0 gap-2">
        <Link
          href={`/documents/${doc.id}`}
          className="rounded-lg border border-slate-200 px-3 py-2 text-[13px] font-medium text-slate-700 hover:bg-slate-50 transition-colors"
        >
          Ver detalle
        </Link>
        <button
          onClick={() => onDelete(doc.id)}
          disabled={deleting}
          className="rounded-lg border border-red-200 px-3 py-2 text-[13px] font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors"
        >
          {deleting ? 'Eliminando…' : 'Eliminar'}
        </button>
      </div>
    </div>
  )
}

export function DocumentDetailSummary({ doc }: { doc: DocumentItem }) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">{cleanFilename(doc.filename)}</h1>
        <StatusChip state={doc.processing_state} />
        <ValueChip label={doc.is_helping ? 'Aporta valor' : 'Sin valor visible'} tone={doc.is_helping ? 'good' : 'warn'} />
      </div>
      <p className="mt-2 text-[14px] leading-relaxed text-slate-500">
        Subido el {formatDate(doc.created_at)}. Esta vista muestra si el documento sirve, cómo se usa y qué conviene hacer con él.
      </p>
    </>
  )
}
