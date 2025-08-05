export interface Transcription {
  id: number;
  filename: string;
  transcription_status: 'pending' | 'processing' | 'completed' | 'error';
  set_language: string;
  meeting_title: string | null;
  meeting_start_date: string | null;
  participants: string | null;
  transcription_duration: number | null;
  audio_duration: number | null;
  created_at: string;
  detected_language: string | null;
  transcript_text: string | null;
  corrected_text: string | null;
  recording_date: string | null;
}

export interface CalendarEntry {
  id: number;
  subject: string;
  start_date: string;
  end_date: string;
  location?: string;
  attendees?: string;
}

export interface WorkflowStatus {
  status: 'active' | 'running' | 'stopped' | 'error';
  message?: string;
}

export interface HealthStatus {
  database: boolean;
  n8n: boolean;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
  error?: string;
}

export interface PaginationParams {
  page: number;
  limit: number;
  search?: string;
  status?: string;
  language?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
} 