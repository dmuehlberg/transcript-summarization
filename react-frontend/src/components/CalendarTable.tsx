
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from './ui/button';
import { transcriptionApi, calendarApi } from '@/lib/api';
import { formatDate } from '@/lib/data-formatters';
import type { CalendarEntry } from '@/lib/types';
import { ArrowLeft, Check } from 'lucide-react';

interface CalendarTableProps {
  transcriptionId: number;
  startDate: string;
  onBack: () => void;
  onSuccess: () => void;
}

export const CalendarTable: React.FC<CalendarTableProps> = ({
  transcriptionId,
  startDate,
  onBack,
  onSuccess,
}) => {
  const queryClient = useQueryClient();

  // Fetch transcription details
  const { data: transcriptionData } = useQuery({
    queryKey: ['transcription', transcriptionId],
    queryFn: () => transcriptionApi.getAll({ page: 1, limit: 1 }),
    select: (data) => data.data.find(t => t.id === transcriptionId),
  });

  // Fetch calendar entries
  const { data: calendarData, isLoading } = useQuery({
    queryKey: ['calendar', startDate],
    queryFn: () => calendarApi.getByDate(startDate),
  });

  // Link calendar mutation
  const linkCalendarMutation = useMutation({
    mutationFn: (calendarEntry: CalendarEntry) =>
      transcriptionApi.linkCalendar(transcriptionId, calendarEntry),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transcriptions'] });
      onSuccess();
    },
  });

  const columnHelper = createColumnHelper<CalendarEntry>();

  const columns = [
    // Subject
    columnHelper.accessor('subject', {
      header: 'Betreff',
      cell: ({ getValue }) => <span className="font-medium">{getValue()}</span>,
    }),
    
    // Start date
    columnHelper.accessor('start_date', {
      header: 'Start',
      cell: ({ getValue }) => <span>{formatDate(getValue())}</span>,
    }),
    
    // End date
    columnHelper.accessor('end_date', {
      header: 'Ende',
      cell: ({ getValue }) => <span>{formatDate(getValue())}</span>,
    }),
    
    // Location
    columnHelper.accessor('location', {
      header: 'Ort',
      cell: ({ getValue }) => <span>{getValue() || '-'}</span>,
    }),
    
    // Attendees
    columnHelper.accessor('attendees', {
      header: 'Teilnehmer',
      cell: ({ getValue }) => <span>{getValue() || '-'}</span>,
    }),
    
    // Actions
    columnHelper.display({
      id: 'actions',
      header: 'Aktion',
      cell: ({ row }) => (
        <Button
          size="sm"
          onClick={() => linkCalendarMutation.mutate(row.original)}
          disabled={linkCalendarMutation.isPending}
          className="flex items-center space-x-1"
        >
          <Check className="h-3 w-3" />
          <span>Auswählen</span>
        </Button>
      ),
    }),
  ];

  const table = useReactTable({
    data: calendarData?.data || [],
    columns,
    state: {
      sorting: [],
    },
    onSortingChange: () => {},
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 rounded-full border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-4">
            <Button variant="outline" onClick={onBack} className="flex items-center space-x-2">
              <ArrowLeft className="h-4 w-4" />
              <span>Zurück</span>
            </Button>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              Kalender-Einträge auswählen
            </h2>
          </div>
        </div>
        
        {/* Transcription Info */}
        {transcriptionData && (
          <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 mb-4">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              Transkription: {transcriptionData.filename}
            </h3>
            <div className="grid grid-cols-2 gap-4 text-sm text-gray-600 dark:text-gray-400">
              <div>
                <span className="font-medium">Status:</span> {transcriptionData.transcription_status}
              </div>
              <div>
                <span className="font-medium">Sprache:</span> {transcriptionData.set_language}
              </div>
              <div>
                <span className="font-medium">Meeting-Datum:</span> {formatDate(transcriptionData.meeting_start_date)}
              </div>
              <div>
                <span className="font-medium">Erstellt:</span> {formatDate(transcriptionData.created_at)}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-700">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider"
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                  Keine Kalender-Einträge für das ausgewählte Datum gefunden.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Error Display */}
      {linkCalendarMutation.isError && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border-t border-red-200 dark:border-red-800">
          <div className="text-sm text-red-700 dark:text-red-400">
            Fehler beim Verknüpfen mit Kalender-Eintrag
          </div>
        </div>
      )}
    </div>
  );
}; 