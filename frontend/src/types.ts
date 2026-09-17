export type RAGMode = 'hybrid' | 'strict' | 'llm-only';

export type Language = 'fa' | 'en';

export type Theme = 'dark' | 'light';
export type ModelProvider = 'api' | 'ollama';

export interface ModelConfiguration {
  provider: ModelProvider;
  model_name: string;
  base_url: string;
  api_key_configured: boolean;
}

export interface OllamaModel { name: string; size?: number | null }

export interface Citation {
  filename: string;
  locations: Array<{ kind: 'page' | 'slide' | 'paragraph' | 'section'; start: number; end?: number }>;
}

export interface ResponseVariant {
  id: string;
  content: string;
  timestamp: number;
  citations?: Citation[];
  error?: boolean;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  citations?: Citation[];
  isStreaming?: boolean;
  error?: boolean;
  variants?: ResponseVariant[];
  activeVariant?: number;
  parentUserId?: string;
}

export interface SessionDocument {
  name: string;
  size?: number;
  status: 'indexed' | 'uploading' | 'processing' | 'error';
  errorMessage?: string;
  enabled?: boolean;
  uploadProgress?: number;
}

export interface Session {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  documents: SessionDocument[];
  messages: Message[];
  ragMode: RAGMode;
  draft?: string;
}

export interface AppSettings {
  language: Language;
  theme: Theme;
  defaultMode: RAGMode;
  strictThreshold: number;
  dynamicDepth: boolean;
  topK: number;
  selectedModel: string;
  apiModelName: string;
  ollamaModelName: string;
  apiBaseUrl: string;
  ollamaBaseUrl: string;
  backendUrl: string;
}
