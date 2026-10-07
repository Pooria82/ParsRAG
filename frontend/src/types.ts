export type RAGMode = 'hybrid' | 'strict' | 'llm-only';

export type Language = 'fa' | 'en';

export type Theme = 'dark' | 'light';
export type Palette = 'evergreen' | 'ocean' | 'indigo' | 'sienna';
export type ModelProvider = 'api' | 'ollama';
export type QueryStage = 'understanding' | 'retrieving' | 'generating' | 'complete' | 'failed';

export interface ModelConfiguration {
  provider: ModelProvider;
  model_name: string;
  base_url: string;
  api_key_configured: boolean;
  disclosure_acknowledged: boolean;
}

export interface OllamaModel { name: string; size?: number | null }

export interface IngestionCapabilities {
  max_files_per_session: number;
  max_file_size_bytes: number;
  max_batch_size_bytes: number;
  supported_extensions: string[];
  ocr_enabled: boolean;
}

export interface AppCapabilities { ingestion: IngestionCapabilities }

export interface SourceLocation { kind: 'page' | 'slide' | 'paragraph' | 'section'; start: number; end?: number }

export interface Citation {
  filename: string;
  locations: SourceLocation[];
}

/** One numbered excerpt given to the model; `cited` when the answer used [n]. */
export interface SourcePassage {
  n: number;
  filename: string;
  location?: SourceLocation;
  text: string;
  cited: boolean;
  score?: number;
}

/** Where an answer's content came from, shown as a badge on the answer. */
export type Grounding = 'documents' | 'hybrid' | 'general' | 'not_found';

export interface ResponseVariant {
  id: string;
  content: string;
  timestamp: number;
  grounding?: Grounding;
  citations?: Citation[];
  sources?: SourcePassage[];
  error?: boolean;
  prompt?: string;
  continuation?: Message[];
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  citations?: Citation[];
  sources?: SourcePassage[];
  grounding?: Grounding;
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
  /** Chunks indexed and pages/slides/paragraphs read, from the ingest response. */
  chunks?: number;
  sections?: number;
  /** Partial-indexing notice codes such as `ocr_page_limit`. */
  notices?: string[];
}

export interface IngestedFile {
  filename: string;
  chunks?: number;
  sections?: number;
  notices: string[];
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
  /** Questions suggested from the indexed documents; `key` names the document set. */
  suggestions?: { key: string; questions: string[] };
}

export interface AppSettings {
  language: Language;
  theme: Theme;
  palette: Palette;
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
