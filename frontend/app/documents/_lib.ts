export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
export const ORG_ID = process.env.NEXT_PUBLIC_ORG_ID ?? '00000000-0000-0000-0000-000000000001'

export type DocumentItem = {
  id: string
  organization_id: string
  filename: string
  status: string
  processing_state: 'processed' | 'pending'
  created_at: string
  chunks_count: number
  usage_count: number
  last_used_at: string | null
  related_active_gaps_count: number
  related_gap_topics: string[]
  is_helping: boolean
}

export type DocumentsOverview = {
  documents: DocumentItem[]
  insights: {
    total_documents: number
    processed_documents: number
    pending_documents: number
    documents_helping_count: number
    unused_documents_count: number
    documents_related_to_gaps_count: number
    most_used: DocumentItem[]
    never_used: DocumentItem[]
    could_resolve_gaps: DocumentItem[]
    recent_documents: DocumentItem[]
  }
}

export type DocumentDetail = DocumentItem & {
  extracted_text: string | null
}

export function cleanFilename(raw: string): string {
  const match = raw.match(/^[0-9a-f-]{36}_(.+)$/i)
  return match ? match[1] : raw
}

export function relativeTime(iso: string | null): string {
  if (!iso) return 'Nunca'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Recién'
  if (mins < 60) return `Hace ${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `Hace ${hrs}h`
  const days = Math.floor(hrs / 24)
  return `Hace ${days}d`
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat('es-AR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(iso))
}
