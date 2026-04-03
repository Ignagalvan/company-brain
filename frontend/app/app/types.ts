export type Citation = {
  id: string
  chunk_id: string | null
  document_id: string
  content: string
  chunk_index: number
  distance: number | null
  created_at: string
}

export type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  model_used: string | null
  created_at: string
  citations: Citation[]
}

export type Conversation = {
  id: string
  title: string
  messages: Message[]
  updated_at: string
}

export type UploadedDoc = {
  id: number
  filename: string
}
