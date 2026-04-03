export type Citation = {
  id: string
  chunk_id: string | null
  document_id: string
  filename: string | null
  content: string
  chunk_index: number
  distance: number | null
  created_at: string
}

export type MessageDebug = {
  raw_chunks_count: number
  relevant_chunks_count: number
  distances: { chunk_index: number; distance: number }[]
  fallback: boolean
  fallback_reason: 'no_relevant_chunks' | 'llm_validation' | null
}

export type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  model_used: string | null
  created_at: string
  citations: Citation[]
  sources_count: number
  documents_count: number
  has_sufficient_evidence: boolean
  is_partial_answer: boolean
  debug?: MessageDebug | null
}

export type Conversation = {
  id: string
  title: string
  messages: Message[]
  updated_at: string
}

export type UploadedDoc = {
  id: string
  filename: string
}
