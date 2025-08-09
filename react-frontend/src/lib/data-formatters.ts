import type { Transcription, CalendarEntry } from './types';

export const formatDuration = (seconds: number | null): string => {
  if (!seconds) return '-';
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
};

export const formatDate = (dateString: string | null): string => {
  if (!dateString) return '-';
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('de-DE', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateString;
  }
};

export const getStatusColor = (status: string): string => {
  switch (status) {
    case 'finished':
      return 'bg-green-500 text-white';
    case 'processing':
      return 'bg-blue-500 text-white';
    case 'pending':
      return 'bg-yellow-500 text-white';
    case 'error':
      return 'bg-red-500 text-white';
    default:
      return 'bg-gray-500 text-white';
  }
};

export const getStatusText = (status: string): string => {
  switch (status) {
    case 'finished':
      return 'Abgeschlossen';
    case 'processing':
      return 'Verarbeitung';
    case 'pending':
      return 'Ausstehend';
    case 'error':
      return 'Fehler';
    default:
      return status;
  }
};

export const truncateText = (text: string | null, maxLength: number = 100): string => {
  if (!text) return '-';
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
};

export const prepareTranscriptionsData = (transcriptions: Transcription[]): Transcription[] => {
  return transcriptions.map(transcription => ({
    ...transcription,
    // Zusätzliche formatierte Felder können hier hinzugefügt werden
  }));
};

export const prepareCalendarData = (calendarEntries: CalendarEntry[]): CalendarEntry[] => {
  return calendarEntries.map(entry => ({
    ...entry,
    // Zusätzliche formatierte Felder können hier hinzugefügt werden
  }));
};

export const getLanguageOptions = (): { value: string; label: string }[] => {
  return [
    { value: 'de', label: 'Deutsch' },
    { value: 'en', label: 'Englisch' },
    { value: 'fr', label: 'Französisch' },
    { value: 'es', label: 'Spanisch' },
    { value: 'it', label: 'Italienisch' },
    { value: 'auto', label: 'Automatisch erkennen' },
  ];
}; 