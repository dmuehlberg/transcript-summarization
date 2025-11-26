import { useState, useEffect } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
  type ColumnFiltersState,
  type ColumnSizingState,
} from '@tanstack/react-table';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Select } from './ui/select';
import { StatusBadge } from './StatusBadge';
import { transcriptionApi, tableConfigApi, calendarApi } from '@/lib/api';
import { formatDuration, formatDate, formatTime, getLanguageOptions } from '@/lib/data-formatters';
import type { CalendarEntry } from '@/lib/types';
import type { Transcription, TableColumnConfig, ColumnSizingState as SavedColumnSizingState } from '@/lib/types';
import { Trash2, Check, X } from 'lucide-react';

interface TranscriptionTableProps {
}

export const TranscriptionTable: React.FC<TranscriptionTableProps> = () => {
  const queryClient = useQueryClient();
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});
  const [globalFilter, setGlobalFilter] = useState('');
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set());
  const [editingCell, setEditingCell] = useState<{ id: number; column: string } | null>(null);
  const [editValue, setEditValue] = useState('');
  // const [savedColumnSizing, setSavedColumnSizing] = useState<SavedColumnSizingState>({});

  // Fetch transcriptions
  const { data: transcriptionsData, isLoading } = useQuery({
    queryKey: ['transcriptions'],
    queryFn: () => transcriptionApi.getAll(),
    refetchInterval: 10000, // Alle 10 Sekunden
  });

  // Load column configuration
  const { data: columnConfig, isLoading: configLoading, error: configError } = useQuery({
    queryKey: ['table-config', 'transcriptions'],
    queryFn: () => tableConfigApi.getConfig('transcriptions'),
    staleTime: 5 * 60 * 1000, // 5 Minuten
    retry: 3,
  });

  // Update language mutation
  const updateLanguageMutation = useMutation({
    mutationFn: ({ id, language }: { id: number; language: string }) =>
      transcriptionApi.updateLanguage(id, language),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transcriptions'] });
      setEditingCell(null);
    },
  });

  // Delete transcriptions mutation
  const deleteTranscriptionsMutation = useMutation({
    mutationFn: (ids: number[]) => {
      console.log('Mutation function called with IDs:', ids);
      return transcriptionApi.deleteMultiple(ids);
    },
    onSuccess: (_, variables) => {
      console.log('Delete mutation successful, deleted IDs:', variables);
      queryClient.invalidateQueries({ queryKey: ['transcriptions'] });
      setSelectedRows(new Set());
    },
    onError: (error, variables) => {
      console.error('Delete mutation failed for IDs:', variables, 'Error:', error);
    },
  });

  // Save column configuration mutation
  const saveColumnConfigMutation = useMutation({
    mutationFn: (columns: TableColumnConfig[]) => {
      return tableConfigApi.updateConfig('transcriptions', columns);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['table-config', 'transcriptions'] });
    },
    onError: (error) => {
      console.error('Failed to save column configuration:', error);
    },
  });

  // Load saved column configuration on mount
  useEffect(() => {
    if (columnConfig?.data) {
      const configMap: SavedColumnSizingState = {};
      columnConfig.data.forEach(col => {
        if (col.is_visible) {
          configMap[col.column_name] = col.column_width;
        }
      });
      setColumnSizing(configMap);
      // setSavedColumnSizing(configMap);
    }
  }, [columnConfig]);

  // Find all unique dates for transcriptions with "Mehrere Meetings gefunden"
  const transcriptionsWithMultipleMeetings = transcriptionsData?.data?.filter(
    t => t.meeting_title === "Mehrere Meetings gefunden" && t.recording_date
  ) || [];
  
  const uniqueDates = Array.from(
    new Set(
      transcriptionsWithMultipleMeetings.map(t => {
        if (!t.recording_date) return null;
        const date = new Date(t.recording_date);
        return date.toISOString().split('T')[0]; // YYYY-MM-DD
      }).filter(Boolean) as string[]
    )
  );

  // Fetch meetings for each unique date using individual queries
  // Note: React Hooks rules require hooks to be called in the same order.
  // We'll create queries for up to 10 unique dates (should be sufficient for most cases)
  const meetingsByDate = new Map<string, CalendarEntry[]>();
  
  // Create queries for each unique date (limited to 10 to prevent too many queries)
  const datesToQuery = uniqueDates.slice(0, 10);
  
  const query1 = useQuery({
    queryKey: ['calendar-day', datesToQuery[0]],
    queryFn: () => calendarApi.getByDay(datesToQuery[0]!),
    enabled: !!datesToQuery[0],
  });
  const query2 = useQuery({
    queryKey: ['calendar-day', datesToQuery[1]],
    queryFn: () => calendarApi.getByDay(datesToQuery[1]!),
    enabled: !!datesToQuery[1],
  });
  const query3 = useQuery({
    queryKey: ['calendar-day', datesToQuery[2]],
    queryFn: () => calendarApi.getByDay(datesToQuery[2]!),
    enabled: !!datesToQuery[2],
  });
  const query4 = useQuery({
    queryKey: ['calendar-day', datesToQuery[3]],
    queryFn: () => calendarApi.getByDay(datesToQuery[3]!),
    enabled: !!datesToQuery[3],
  });
  const query5 = useQuery({
    queryKey: ['calendar-day', datesToQuery[4]],
    queryFn: () => calendarApi.getByDay(datesToQuery[4]!),
    enabled: !!datesToQuery[4],
  });
  const query6 = useQuery({
    queryKey: ['calendar-day', datesToQuery[5]],
    queryFn: () => calendarApi.getByDay(datesToQuery[5]!),
    enabled: !!datesToQuery[5],
  });
  const query7 = useQuery({
    queryKey: ['calendar-day', datesToQuery[6]],
    queryFn: () => calendarApi.getByDay(datesToQuery[6]!),
    enabled: !!datesToQuery[6],
  });
  const query8 = useQuery({
    queryKey: ['calendar-day', datesToQuery[7]],
    queryFn: () => calendarApi.getByDay(datesToQuery[7]!),
    enabled: !!datesToQuery[7],
  });
  const query9 = useQuery({
    queryKey: ['calendar-day', datesToQuery[8]],
    queryFn: () => calendarApi.getByDay(datesToQuery[8]!),
    enabled: !!datesToQuery[8],
  });
  const query10 = useQuery({
    queryKey: ['calendar-day', datesToQuery[9]],
    queryFn: () => calendarApi.getByDay(datesToQuery[9]!),
    enabled: !!datesToQuery[9],
  });
  
  // Map query results to dates
  const queries = [query1, query2, query3, query4, query5, query6, query7, query8, query9, query10];
  queries.forEach((query, index) => {
    const date = datesToQuery[index];
    if (date && query.data?.data) {
      meetingsByDate.set(date, query.data.data);
    }
  });

  // Link calendar mutation
  const linkCalendarMutation = useMutation({
    mutationFn: ({ id, calendarEntry }: { id: number; calendarEntry: CalendarEntry }) =>
      transcriptionApi.linkCalendar(id, calendarEntry),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transcriptions'] });
    },
  });



  const columnHelper = createColumnHelper<Transcription>();

  const columns = [
    // Checkbox column
    columnHelper.display({
      id: 'select',
      size: 50,
      minSize: 40,
      enableResizing: true,
      header: ({ table }) => (
        <input
          type="checkbox"
          checked={table.getIsAllPageRowsSelected()}
          onChange={table.getToggleAllPageRowsSelectedHandler()}
          className="rounded border-gray-300"
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={row.getIsSelected()}
          onChange={row.getToggleSelectedHandler()}
          className="rounded border-gray-300"
        />
      ),
    }),
    
    // Filename
    columnHelper.accessor('filename', {
      header: 'Dateiname',
      size: 200,
      minSize: 150,
      enableResizing: true,
      cell: ({ getValue }) => <span>{getValue()}</span>,
    }),
    
    // Status
    columnHelper.accessor('transcription_status', {
      header: 'Status',
      size: 120,
      minSize: 100,
      enableResizing: true,
      cell: ({ getValue }) => <StatusBadge status={getValue()} />,
    }),
    
    // Language (Inline editable)
    columnHelper.accessor('set_language', {
      header: 'Sprache',
      size: 150,
      minSize: 120,
      enableResizing: true,
      cell: ({ row, getValue }) => {
        const isEditing = editingCell?.id === row.original.id && editingCell?.column === 'set_language';
        const languageOptions = getLanguageOptions();
        const currentValue = getValue();
        
        if (isEditing) {
          // Sicherstellen, dass editValue einen gültigen Wert hat
          // Verwende editValue, falls gesetzt, sonst den aktuellen Wert oder den ersten Optionenwert
          const validValue = editValue || currentValue || languageOptions[0]?.value || 'auto';
          
          return (
            <div className="flex items-center space-x-2">
              <Select
                value={validValue}
                onChange={(e) => setEditValue(e.target.value)}
                className="w-32"
              >
                {languageOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
              <Button
                size="sm"
                onClick={() => {
                  // Verwende den Wert, der im Select-Element angezeigt wird (validValue)
                  // Das stellt sicher, dass der korrekte Wert gespeichert wird, auch wenn editValue noch nicht aktualisiert wurde
                  updateLanguageMutation.mutate({ id: row.original.id, language: validValue });
                }}
                disabled={updateLanguageMutation.isPending}
              >
                <Check className="h-3 w-3" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setEditingCell(null)}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          );
        }
        
        return (
          <div className="flex items-center space-x-2">
            <span>{getValue()}</span>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setEditingCell({ id: row.original.id, column: 'set_language' });
                // Verwende den aktuellen Wert oder den ersten Optionenwert als Fallback
                const initialValue = currentValue || languageOptions[0]?.value || 'auto';
                setEditValue(initialValue);
              }}
            >
              Bearbeiten
            </Button>
          </div>
        );
      },
    }),
    
    // Meeting title
    columnHelper.accessor('meeting_title', {
      header: 'Meeting-Titel',
      size: 200,
      minSize: 150,
      enableResizing: true,
      cell: ({ row, getValue }) => {
        const meetingTitle = getValue();
        const transcription = row.original;
        
        // Prüfe ob mehrere Meetings gefunden
        if (meetingTitle === "Mehrere Meetings gefunden") {
          // Extrahiere Datum aus recording_date
          const recordingDate = transcription.recording_date;
          if (!recordingDate) {
            return <span className="text-gray-500">Kein Datum verfügbar</span>;
          }
          
          const dateOnly = new Date(recordingDate).toISOString().split('T')[0];
          const meetings = meetingsByDate.get(dateOnly) || [];
          
          // Finde den aktuell ausgewählten Meeting-Index (falls bereits verknüpft)
          const selectedMeetingIndex = meetings.findIndex(
            m => m.start_date === transcription.meeting_start_date
          );
          
          return (
            <Select
              value={selectedMeetingIndex >= 0 ? selectedMeetingIndex.toString() : ''}
              onChange={(e) => {
                const index = parseInt(e.target.value);
                if (index >= 0 && index < meetings.length) {
                  const selectedMeeting = meetings[index];
                  linkCalendarMutation.mutate({
                    id: transcription.id,
                    calendarEntry: {
                      subject: selectedMeeting.subject,
                      start_date: selectedMeeting.start_date,
                      end_date: selectedMeeting.end_date,
                      location: selectedMeeting.location,
                      attendees: selectedMeeting.attendees,
                    }
                  });
                }
              }}
              disabled={linkCalendarMutation.isPending}
              className="w-full"
            >
              <option value="">Bitte wählen...</option>
              {meetings.map((meeting, index) => (
                <option key={index} value={index.toString()}>
                  {formatTime(meeting.start_date)} - {meeting.subject}
                </option>
              ))}
            </Select>
          );
        }
        
        // Normale Anzeige
        return <span>{meetingTitle || '-'}</span>;
      },
    }),
    
    // Meeting start date
    columnHelper.accessor('meeting_start_date', {
      header: 'Meeting-Datum',
      size: 120,
      minSize: 100,
      enableResizing: true,
      cell: ({ getValue }) => <span>{formatDate(getValue())}</span>,
    }),
    
    // Participants
    columnHelper.accessor('participants', {
      header: 'Teilnehmer',
      size: 150,
      minSize: 120,
      enableResizing: true,
      cell: ({ getValue }) => <span>{getValue()}</span>,
    }),
    
    // Transcription duration
    columnHelper.accessor('transcription_duration', {
      header: 'Transkription',
      size: 120,
      minSize: 100,
      enableResizing: true,
      cell: ({ getValue }) => <span>{formatDuration(getValue())}</span>,
    }),
    
    // Audio duration
    columnHelper.accessor('audio_duration', {
      header: 'Audio',
      size: 100,
      minSize: 80,
      enableResizing: true,
      cell: ({ getValue }) => <span>{formatDuration(getValue())}</span>,
    }),
    
    // Created at
    columnHelper.accessor('created_at', {
      header: 'Erstellt',
      size: 120,
      minSize: 100,
      enableResizing: true,
      cell: ({ getValue }) => <span>{formatDate(getValue())}</span>,
    }),
  ];



  const table = useReactTable({
    data: transcriptionsData?.data || [],
    columns,
    state: {
      sorting,
      columnFilters,
      columnSizing,
      globalFilter,
      rowSelection: Object.fromEntries(
        (transcriptionsData?.data || []).map((row, index) => [
          index.toString(),
          selectedRows.has(row.id)
        ])
      ),
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnSizingChange: (updater: any) => {
      const newSizing = typeof updater === 'function' ? updater(columnSizing) : updater;
      setColumnSizing(newSizing);
      
      // Clear any existing timeout
      if ((window as any).columnResizeTimeout) {
        clearTimeout((window as any).columnResizeTimeout);
      }
      
      // Save to database after a longer delay (better debouncing)
      (window as any).columnResizeTimeout = setTimeout(() => {
        if (columnConfig?.data) {
          const updatedColumns = columnConfig.data.map(col => {
            const newWidth = newSizing[col.column_name];
            if (newWidth !== undefined) {
              return {
                ...col,
                column_width: newWidth
              };
            }
            return col;
          });
          
          saveColumnConfigMutation.mutate(updatedColumns);
        }
      }, 1000); // Increased to 1 second for better debouncing
    },
    onGlobalFilterChange: setGlobalFilter,
    onRowSelectionChange: (updater) => {
      const newSelection = typeof updater === 'function' ? updater({}) : updater;
      console.log('Raw selection change:', newSelection);
      
      // Get current selected rows to merge with new selection
      const currentSelectedRows = new Map(
        Array.from(selectedRows).map(id => [id, true])
      );
      
      // Process new selection changes
      Object.entries(newSelection).forEach(([rowIndexStr, isSelected]) => {
        const rowIndex = parseInt(rowIndexStr);
        const row = table.getRowModel().rows[rowIndex];
        const transcriptionId = row?.original?.id;
        
        if (transcriptionId) {
          console.log(`Row ${rowIndex} -> ID: ${transcriptionId} -> Selected: ${isSelected}`);
          
          if (isSelected) {
            currentSelectedRows.set(transcriptionId, true);
          } else {
            currentSelectedRows.delete(transcriptionId);
          }
        }
      });
      
      const newSelectedIds = Array.from(currentSelectedRows.keys());
      console.log('Updated selection, all selected IDs:', newSelectedIds);
      setSelectedRows(new Set(newSelectedIds));
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    columnResizeMode: 'onChange',
    enableColumnResizing: true,
    enableRowSelection: true,
    enableMultiRowSelection: true,
  });

  const handleDeleteSelected = () => {
    console.log('Delete button clicked, selectedRows:', selectedRows);
    if (selectedRows.size > 0) {
      const ids = Array.from(selectedRows);
      console.log('Deleting transcriptions with IDs:', ids);
      deleteTranscriptionsMutation.mutate(ids);
    } else {
      console.log('No rows selected for deletion');
    }
  };

  // Zeige Loading-Indikator während Konfiguration geladen wird
  if (configLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 rounded-full border-t-transparent"></div>
        <span className="ml-2">Lade Tabellenkonfiguration...</span>
      </div>
    );
  }

  // Zeige Fehlermeldung bei Problemen
  if (configError) {
    // Fallback zu Standard-Spaltenbreiten
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 rounded-full border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Table Header with Filters */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Transkriptionen
          </h2>
          <div className="flex items-center space-x-2">
            <Input
              placeholder="Suchen..."
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              className="w-64"
            />
            {selectedRows.size > 0 && (
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDeleteSelected}
                disabled={deleteTranscriptionsMutation.isPending}
              >
                <Trash2 className="h-4 w-4 mr-1" />
                {selectedRows.size} löschen
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full table-fixed">
          <thead className="bg-gray-50 dark:bg-gray-700">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider relative overflow-hidden"
                    style={{ 
                      width: header.getSize(),
                      minWidth: header.getSize(),
                      maxWidth: header.getSize()
                    }}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                    {header.column.getCanResize() && (
                      <div
                        onMouseDown={header.getResizeHandler()}
                        onTouchStart={header.getResizeHandler()}
                        className={`absolute right-0 top-0 h-full w-1 cursor-col-resize select-none touch-none ${
                          header.column.getIsResizing() ? 'bg-blue-500' : 'bg-gray-300 hover:bg-gray-400'
                        }`}
                      />
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                {row.getVisibleCells().map((cell) => (
                  <td 
                    key={cell.id} 
                    className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 overflow-hidden"
                    style={{ 
                      width: cell.column.getSize(),
                      minWidth: cell.column.getSize(),
                      maxWidth: cell.column.getSize()
                    }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Seite {table.getState().pagination.pageIndex + 1} von{' '}
              {table.getPageCount()}
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              Zurück
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              Weiter
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}; 