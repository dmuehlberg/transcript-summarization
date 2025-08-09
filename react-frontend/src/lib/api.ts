import axios from 'axios';
import type { 
  Transcription, 
  CalendarEntry, 
  WorkflowStatus, 
  HealthStatus,
  PaginationParams,
  PaginatedResponse,
  ApiResponse 
} from './types';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor für Logging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor für Error Handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// Transcription APIs
export const transcriptionApi = {
  getAll: async (params?: PaginationParams): Promise<PaginatedResponse<Transcription>> => {
    const response = await api.get('/transcriptions', { params });
    return response.data;
  },

  deleteMultiple: async (ids: number[]): Promise<ApiResponse<void>> => {
    const response = await api.delete('/transcriptions', { data: { ids } });
    return response.data;
  },

  updateLanguage: async (id: number, language: string): Promise<ApiResponse<Transcription>> => {
    const response = await api.patch(`/transcriptions/${id}/language`, { language });
    return response.data;
  },

  linkCalendar: async (id: number, calendarData: Partial<CalendarEntry>): Promise<ApiResponse<Transcription>> => {
    const response = await api.post(`/transcriptions/${id}/link-calendar`, calendarData);
    return response.data;
  },
};

// Calendar APIs
export const calendarApi = {
  getByDate: async (startDate: string): Promise<ApiResponse<CalendarEntry[]>> => {
    const response = await api.get('/calendar', { params: { start_date: startDate } });
    return response.data;
  },
};

// Workflow APIs
export const workflowApi = {
  start: async (): Promise<ApiResponse<void>> => {
    const response = await api.post('/workflow/start');
    return response.data;
  },

  getStatus: async (): Promise<ApiResponse<WorkflowStatus>> => {
    const response = await api.get('/workflow/status');
    return response.data;
  },
};

// Health API
export const healthApi = {
  check: async (): Promise<ApiResponse<HealthStatus>> => {
    const response = await api.get('/health');
    return response.data;
  },
};

export default api; 