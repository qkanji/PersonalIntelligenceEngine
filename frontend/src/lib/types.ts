export interface Source {
  score: number;
  text_preview: string;
  notebook: string;
  section: string;
  page: string;
  source_pdf: string;
  chunk: number;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}
