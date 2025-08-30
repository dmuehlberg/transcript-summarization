# Implementierungskonzept: Spaltenbreiten-Speicherung in React-Tabellen

## Übersicht
Dieses Dokument beschreibt die vollständige Implementierung zur Speicherung von Spaltenbreiten in React-Tabellen in der Datenbank. Die Implementierung ermöglicht es Benutzern, ihre bevorzugten Spaltenbreiten zu speichern und bei der nächsten Nutzung wiederherzustellen.

## 1. Datenbankstruktur

### 1.1 Tabelle für Spaltenkonfiguration
```sql
CREATE TABLE IF NOT EXISTS react_table_column_config (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    column_name VARCHAR(100) NOT NULL,
    column_width INTEGER NOT NULL,
    column_order INTEGER NOT NULL,
    is_visible BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_name, column_name)
);
```

### 1.2 Indizes für bessere Performance
```sql
CREATE INDEX IF NOT EXISTS idx_react_table_column_config_table ON react_table_column_config(table_name);
CREATE INDEX IF NOT EXISTS idx_react_table_column_config_order ON react_table_column_config(table_name, column_order);
```

### 1.3 Standard-Spaltenkonfiguration für Transkriptions-Tabelle
```sql
INSERT INTO react_table_column_config (table_name, column_name, column_width, column_order, is_visible) VALUES
('transcriptions', 'select', 50, 1, true),
('transcriptions', 'filename', 200, 2, true),
('transcriptions', 'transcription_status', 120, 3, true),
('transcriptions', 'set_language', 150, 4, true),
('transcriptions', 'meeting_title', 200, 5, true),
('transcriptions', 'meeting_start_date', 120, 6, true),
('transcriptions', 'participants', 200, 7, true),
('transcriptions', 'transcription_duration', 120, 8, true),
('transcriptions', 'audio_duration', 120, 9, true),
('transcriptions', 'detected_language', 120, 10, true),
('transcriptions', 'created_at', 120, 11, true),
('transcriptions', 'actions', 150, 12, true)
ON CONFLICT (table_name, column_name) DO UPDATE SET
    column_width = EXCLUDED.column_width,
    column_order = EXCLUDED.column_order,
    updated_at = CURRENT_TIMESTAMP;
```

## 2. Backend-API-Endpoints (server.js)

### 2.1 Spaltenkonfiguration abrufen
```javascript
// Get column configuration for a table
app.get('/api/table-config/:tableName', async (req, res) => {
  try {
    const { tableName } = req.params;
    
    const query = `
      SELECT column_name, column_width, column_order, is_visible
      FROM react_table_column_config 
      WHERE table_name = $1 
      ORDER BY column_order
    `;
    
    const result = await pool.query(query, [tableName]);
    
    res.json({
      data: result.rows,
      message: `Column configuration loaded for ${tableName}`
    });
  } catch (error) {
    logger.error('Failed to load column configuration:', error);
    res.status(500).json({
      error: 'Failed to load column configuration',
      details: error.message
    });
  }
});
```

### 2.2 Spaltenkonfiguration aktualisieren
```javascript
// Update column configuration
app.put('/api/table-config/:tableName', async (req, res) => {
  try {
    const { tableName } = req.params;
    const { columns } = req.body; // Array of { column_name, column_width, column_order, is_visible }
    
    // Begin transaction
    const client = await pool.connect();
    
    try {
      await client.query('BEGIN');
      
      // Update each column configuration
      for (const column of columns) {
        const updateQuery = `
          INSERT INTO react_table_column_config (table_name, column_name, column_width, column_order, is_visible, updated_at)
          VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
          ON CONFLICT (table_name, column_name) 
          DO UPDATE SET
            column_width = EXCLUDED.column_width,
            column_order = EXCLUDED.column_order,
            is_visible = EXCLUDED.is_visible,
            updated_at = CURRENT_TIMESTAMP
        `;
        
        await client.query(updateQuery, [
          tableName,
          column.column_name,
          column.column_width,
          column.column_order,
          column.is_visible
        ]);
      }
      
      await client.query('COMMIT');
      
      res.json({
        message: `Column configuration updated for ${tableName}`,
        data: { updatedColumns: columns.length }
      });
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  } catch (error) {
    logger.error('Failed to update column configuration:', error);
    res.status(500).json({
      error: 'Failed to update column configuration',
      details: error.message
    });
  }
});
```

## 3. Frontend-Types erweitern (types.ts)

### 3.1 Neue Interfaces hinzufügen
```typescript
export interface TableColumnConfig {
  column_name: string;
  column_width: number;
  column_order: number;
  is_visible: boolean;
}

export interface ColumnSizingState {
  [key: string]: number;
}
```

## 4. Frontend-API erweitern (api.ts)

### 4.1 Neue API-Funktionen
```typescript
// Table Configuration APIs
export const tableConfigApi = {
  getConfig: async (tableName: string): Promise<ApiResponse<TableColumnConfig[]>> => {
    const response = await api.get(`/table-config/${tableName}`);
    return response.data;
  },
  
  updateConfig: async (tableName: string, columns: TableColumnConfig[]): Promise<ApiResponse<void>> => {
    const response = await api.put(`/table-config/${tableName}`, { columns });
    return response.data;
  },
};
```

## 5. TranscriptionTable erweitern (TranscriptionTable.tsx)

### 5.1 Neue Imports und State
```typescript
import { useState, useEffect } from 'react';
// ... existing imports ...
import { tableConfigApi } from '@/lib/api';
import type { TableColumnConfig, ColumnSizingState } from '@/lib/types';

export const TranscriptionTable: React.FC<TranscriptionTableProps> = ({ onSelectMeeting }) => {
  // ... existing state ...
  const [savedColumnSizing, setSavedColumnSizing] = useState<ColumnSizingState>({});
  
  // ... existing code ...
}
```

### 5.2 Spaltenkonfiguration laden
```typescript
// Load column configuration
const { data: columnConfig, isLoading: configLoading, error: configError } = useQuery({
  queryKey: ['table-config', 'transcriptions'],
  queryFn: () => tableConfigApi.getConfig('transcriptions'),
  staleTime: 5 * 60 * 1000, // 5 Minuten
  retry: 3,
});
```

### 5.3 Mutation für das Speichern
```typescript
// Save column configuration mutation
const saveColumnConfigMutation = useMutation({
  mutationFn: (columns: TableColumnConfig[]) =>
    tableConfigApi.updateConfig('transcriptions', columns),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['table-config', 'transcriptions'] });
  },
});
```

### 5.4 Spaltenkonfiguration beim Laden anwenden
```typescript
// Load saved column configuration on mount
useEffect(() => {
  if (columnConfig?.data) {
    const configMap: ColumnSizingState = {};
    columnConfig.data.forEach(col => {
      if (col.is_visible) {
        configMap[col.column_name] = col.column_width;
      }
    });
    setColumnSizing(configMap);
    setSavedColumnSizing(configMap);
  }
}, [columnConfig]);
```

### 5.5 Spaltenbreiten-Änderungen verarbeiten
```typescript
// Save column configuration when column sizing changes
const handleColumnSizingChange = (updater: any) => {
  const newSizing = typeof updater === 'function' ? updater(columnSizing) : updater;
  setColumnSizing(newSizing);
  
  // Save to database after a short delay (debouncing)
  setTimeout(() => {
    if (columnConfig?.data) {
      const updatedColumns = columnConfig.data.map(col => ({
        ...col,
        column_width: newSizing[col.column_name] || col.column_width
      }));
      saveColumnConfigMutation.mutate(updatedColumns);
    }
  }, 500);
};
```

### 5.6 Table-Konfiguration aktualisieren
```typescript
const table = useReactTable({
  data: transcriptionsData?.data || [],
  columns,
  state: {
    sorting,
    columnFilters,
    columnSizing,
    globalFilter,
    rowSelection: Object.fromEntries(
      Array.from(selectedRows).map(id => [id, true])
    ),
  },
  onSortingChange: setSorting,
  onColumnFiltersChange: setColumnFilters,
  onColumnSizingChange: handleColumnSizingChange, // Hier die neue Funktion verwenden
  onGlobalFilterChange: setGlobalFilter,
  onRowSelectionChange: (updater) => {
    const newSelection = typeof updater === 'function' ? updater({}) : updater;
    setSelectedRows(new Set(Object.keys(newSelection).map(Number)));
  },
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
  getFilteredRowModel: getFilteredRowModel(),
  getPaginationRowModel: getPaginationRowModel(),
  columnResizeMode: 'onChange',
  enableColumnResizing: true,
});
```

### 5.7 Loading und Error States
```typescript
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
  console.error('Failed to load column configuration:', configError);
  // Fallback zu Standard-Spaltenbreiten
}
```

## 6. Erweiterte Features (Optional)

### 6.1 Optimistic Updates
```typescript
const saveColumnConfigMutation = useMutation({
  mutationFn: (columns: TableColumnConfig[]) =>
    tableConfigApi.updateConfig('transcriptions', columns),
  onMutate: async (newColumns) => {
    // Optimistic update
    await queryClient.cancelQueries({ queryKey: ['table-config', 'transcriptions'] });
    const previousConfig = queryClient.getQueryData(['table-config', 'transcriptions']);
    
    queryClient.setQueryData(['table-config', 'transcriptions'], {
      data: newColumns,
      message: 'Column configuration updated'
    });
    
    return { previousConfig };
  },
  onError: (err, newColumns, context) => {
    // Rollback bei Fehler
    if (context?.previousConfig) {
      queryClient.setQueryData(['table-config', 'transcriptions'], context.previousConfig);
    }
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['table-config', 'transcriptions'] });
  },
});
```

### 6.2 Spalten-Sichtbarkeit umschalten
```typescript
const toggleColumnVisibility = (columnName: string) => {
  if (columnConfig?.data) {
    const updatedColumns = columnConfig.data.map(col => 
      col.column_name === columnName 
        ? { ...col, is_visible: !col.is_visible }
        : col
    );
    saveColumnConfigMutation.mutate(updatedColumns);
  }
};
```

## 7. Implementierungsreihenfolge

1. **Backend-API-Endpoints**
   - GET `/api/table-config/:tableName` implementieren
   - PUT `/api/table-config/:tableName` implementieren
   - Error Handling und Logging hinzufügen

3. **Frontend-Types**
   - `TableColumnConfig` Interface hinzufügen
   - `ColumnSizingState` Interface hinzufügen

4. **Frontend-API**
   - `tableConfigApi.getConfig()` implementieren
   - `tableConfigApi.updateConfig()` implementieren

5. **TranscriptionTable-Komponente**
   - Spaltenkonfiguration laden
   - Mutation für das Speichern implementieren
   - `handleColumnSizingChange` Funktion implementieren
   - Table-Konfiguration aktualisieren

