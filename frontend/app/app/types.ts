export type Source = {
  chunk_id: string
  document_id: string
  filename: string
  chunk_index: number
  content: string
  distance: number
}

export type Message = {
  id: number
  type: 'user' | 'system'
  content: string
  sources?: Source[]
}

export type Conversation = {
  id: string
  title: string
  messages: Message[]
}

export type UploadedDoc = {
  id: number
  filename: string
}
