export type RAGMode = 'hybrid' | 'strict' | 'llm-only';

export type Language = 'fa' | 'en';

export type Theme = 'dark' | 'light';

export interface Citation {
  title: string;
  filename: string;
  body: string;
  score: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  citations?: Citation[];
  isStreaming?: boolean;
  error?: boolean;
}

export interface SessionDocument {
  name: string;
  size?: number;
  status: 'indexed' | 'uploading' | 'error';
  errorMessage?: string;
  enabled?: boolean;
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
  backendUrl: string;
}
