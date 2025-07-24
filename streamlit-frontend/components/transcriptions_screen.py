"""
Screen 1: Transkriptionen Dashboard mit AG Grid Komponenten.
"""
import streamlit as st
import pandas as pd
import logging
from typing import Dict, Any, Optional
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

from database import db_manager
from utils.workflow_utils import n8n_client
from utils.db_utils import prepare_transcriptions_data, format_duration

logger = logging.getLogger(__name__)

def handle_cell_edit(edited_df, original_df):
    """Behandelt Änderungen in editierbaren Zellen."""
    if edited_df is not None and not edited_df.equals(original_df):
        # Finde geänderte Zeilen
        for index, row in edited_df.iterrows():
            original_row = original_df.loc[index]
            if row['set_language'] != original_row['set_language']:
                # Update in Datenbank
                transcription_id = row['id']
                new_language = row['set_language']
                
                if db_manager and db_manager.update_transcription_language(transcription_id, new_language):
                    st.success(f"✅ Sprache für ID {transcription_id} erfolgreich auf '{new_language}' geändert!")
                else:
                    st.error(f"❌ Fehler beim Aktualisieren der Sprache für ID {transcription_id}")
                    # Stelle den ursprünglichen Wert wieder her
                    edited_df.loc[index, 'set_language'] = original_row['set_language']
        
        return edited_df
    return original_df

def render_transcriptions_screen():
    """Rendert den Transkriptionen Screen."""
    
    # Header
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="color: #1f77b4; font-family: 'Roboto', sans-serif; font-size: 2.5rem; font-weight: bold;">
            📝 TRANSCRIPTION DASHBOARD
        </h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Action Buttons
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col1:
        if st.button("🔄 Refresh Table", use_container_width=True, type="primary"):
            st.rerun()
    
    with col2:
        if st.button("▶️ Start Transcription Workflow", use_container_width=True, type="secondary"):
            start_workflow()
    
    with col3:
        if st.button("🗑️ Markierte löschen", use_container_width=True, type="secondary"):
            # Sammle alle ausgewählten IDs
            selected_ids = []
            for key in st.session_state:
                if key.startswith("checkbox_") and st.session_state[key]:
                    try:
                        transcription_id = int(key.replace("checkbox_", ""))
                        selected_ids.append(transcription_id)
                    except ValueError:
                        pass
            
            if not selected_ids:
                st.warning("Keine Transkriptionen zum Löschen ausgewählt.")
            else:
                # Führe Delete direkt aus
                try:
                    if db_manager:
                        result = db_manager.delete_transcriptions(selected_ids)
                        
                        if result:
                            st.success(f"✅ {len(selected_ids)} Transkription(en) erfolgreich gelöscht!")
                            
                            # Lösche Checkbox-States
                            for transcription_id in selected_ids:
                                checkbox_key = f"checkbox_{transcription_id}"
                                if checkbox_key in st.session_state:
                                    del st.session_state[checkbox_key]
                            
                            st.rerun()
                        else:
                            st.error("❌ Fehler beim Löschen der Transkriptionen")
                    else:
                        st.error("❌ Datenbankmanager nicht verfügbar")
                except Exception as e:
                    st.error(f"❌ Fehler beim Löschen: {str(e)}")
    
    with col4:
        st.write("")  # Spacer
    
    # Lade Transkriptionsdaten
    with st.spinner("Lade Transkriptionen..."):
        transcriptions = db_manager.get_transcriptions()
    
    if not transcriptions:
        st.warning("Keine Transkriptionen gefunden.")
        return
    
    # Bereite Daten für AG-Grid vor
    df = prepare_transcriptions_data(transcriptions)
    
    if df.empty:
        st.warning("Keine Daten zum Anzeigen verfügbar.")
        return
    
    # Erstelle eine interaktive Tabelle mit AG Grid
    st.subheader("📊 Transkriptionen Tabelle")
    
    # Filter-Optionen
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox(
            "Status Filter",
            ["Alle"] + list(df['transcription_status'].unique()) if 'transcription_status' in df.columns else ["Alle"]
        )
    with col2:
        language_filter = st.selectbox(
            "Sprache Filter", 
            ["Alle"] + list(df['set_language'].unique()) if 'set_language' in df.columns else ["Alle"]
        )
    with col3:
        search_term = st.text_input("🔍 Suche", placeholder="Dateiname oder Meeting-Titel...")
    
    # Filtere Daten
    filtered_df = df.copy()
    if status_filter != "Alle" and 'transcription_status' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['transcription_status'] == status_filter]
    if language_filter != "Alle" and 'set_language' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['set_language'] == language_filter]
    if search_term:
        mask = (
            filtered_df['filename'].str.contains(search_term, case=False, na=False) |
            filtered_df['meeting_title'].str.contains(search_term, case=False, na=False)
        )
        filtered_df = filtered_df[mask]
    
    # Zeige gefilterte Daten
    if not filtered_df.empty:
        # AG Grid Konfiguration
        gb = GridOptionsBuilder.from_dataframe(
            filtered_df[['id', 'filename', 'transcription_status', 'set_language', 'meeting_title', 'meeting_start_date']],
            enableRowGroup=True,
            enableValue=True,
            enableRangeSelection=True,
            enableColResize=True,
            enableFilter=True,
            enableSort=True,
            pagination=True,
            paginationPageSize=20,
            domLayout='normal'
        )
        
        # Konfiguriere editierbare set_language Spalte
        gb.configure_column(
            "set_language",
            header_name="Sprache",
            editable=True,
            cellEditor='agSelectCellEditor',
            cellEditorParams={
                'values': ['de', 'en', 'fr', 'es', 'it']
            },
            width=100
        )
        
        # Konfiguriere andere Spalten
        gb.configure_column("id", header_name="ID", width=80, hide=True)
        gb.configure_column("filename", header_name="Dateiname", width=200)
        gb.configure_column("transcription_status", header_name="Status", width=120)
        gb.configure_column("meeting_title", header_name="Meeting Titel", width=250)
        gb.configure_column("meeting_start_date", header_name="Start Datum", width=150)
        
        # Aktiviere Row Selection - verwende single selection für bessere Kompatibilität
        gb.configure_selection(selection_mode='single', use_checkbox=True)
        
        grid_options = gb.build()
        
        # Zeige AG Grid
        grid_response = AgGrid(
            filtered_df[['id', 'filename', 'transcription_status', 'set_language', 'meeting_title', 'meeting_start_date']],
            gridOptions=grid_options,
            data_return_mode=DataReturnMode.AS_INPUT,
            update_mode=GridUpdateMode.MODEL_CHANGED,
            fit_columns_on_grid_load=True,
            theme='streamlit',
            height=400,
            allow_unsafe_jscode=True,
            custom_css={
                ".ag-row-hover": {"background-color": "lightblue !important"},
                ".ag-row-selected": {"background-color": "#e6f3ff !important"}
            }
        )
        
        # Behandle Zellenänderungen
        if 'previous_df' not in st.session_state:
            st.session_state.previous_df = filtered_df[['id', 'filename', 'transcription_status', 'set_language', 'meeting_title', 'meeting_start_date']].copy()
        
        # Debug: Zeige grid_response Struktur
        st.write("🔍 Debug Info:")
        st.write(f"grid_response Typ: {type(grid_response)}")
        if hasattr(grid_response, '__dict__'):
            st.write(f"grid_response Attribute: {list(grid_response.__dict__.keys())}")
        elif isinstance(grid_response, dict):
            st.write(f"grid_response Keys: {list(grid_response.keys())}")
        
        # Extrahiere Daten und ausgewählte Zeilen - streamlit-aggrid gibt ein Objekt zurück
        current_df = None
        selected_rows = []
        
        # Prüfe verschiedene mögliche Strukturen
        if hasattr(grid_response, 'data'):
            current_df = pd.DataFrame(grid_response.data) if grid_response.data is not None else None
            st.write(f"✅ Daten gefunden über .data: {len(current_df) if current_df is not None else 0} Zeilen")
        elif isinstance(grid_response, dict) and 'data' in grid_response:
            current_df = pd.DataFrame(grid_response['data']) if grid_response['data'] is not None else None
            st.write(f"✅ Daten gefunden über ['data']: {len(current_df) if current_df is not None else 0} Zeilen")
        
        if hasattr(grid_response, 'selected_rows'):
            selected_rows = grid_response.selected_rows or []
            st.write(f"✅ selected_rows gefunden über .selected_rows: {len(selected_rows)} Zeilen")
        elif isinstance(grid_response, dict) and 'selected_rows' in grid_response:
            selected_rows = grid_response['selected_rows'] or []
            st.write(f"✅ selected_rows gefunden über ['selected_rows']: {len(selected_rows)} Zeilen")
        
        # Behandle Zellenänderungen
        if current_df is not None and not current_df.equals(st.session_state.previous_df):
            updated_df = handle_cell_edit(current_df, st.session_state.previous_df)
            st.session_state.previous_df = updated_df.copy()
        
        # Zeige ausgewählte Zeilen
        if selected_rows:
            st.subheader(f"📋 Ausgewählte Zeilen ({len(selected_rows)})")
            selected_df = pd.DataFrame(selected_rows)
            st.dataframe(selected_df[['filename', 'transcription_status', 'set_language', 'meeting_title']])
        
        # Zeige Details für ausgewählte Zeile
        if selected_rows:
            st.subheader("📝 Details")
            selected_row = selected_rows[0]  # Zeige Details der ersten ausgewählten Zeile
            
            # Details in Spalten anzeigen
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Dateiname:**", selected_row['filename'])
                st.write("**Status:**", selected_row['transcription_status'])
                st.write("**Sprache:**", selected_row['set_language'])
                st.write("**Meeting Titel:**", selected_row['meeting_title'])
            
            with col2:
                st.write("**Start Datum:**", selected_row['meeting_start_date'])
                # Hole zusätzliche Details aus der ursprünglichen DataFrame
                original_row = filtered_df[filtered_df['id'] == selected_row['id']].iloc[0] if len(filtered_df[filtered_df['id'] == selected_row['id']]) > 0 else None
                if original_row is not None:
                    st.write("**Teilnehmer:**", original_row.get('participants', 'N/A'))
                    st.write("**Audio Dauer:**", format_duration(original_row.get('audio_duration')))
                    st.write("**Erstellt:**", original_row.get('created_at', 'N/A'))
            
            # Aktionen
            st.subheader("⚡ Aktionen")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Meeting auswählen
                if st.button("📅 Meeting auswählen"):
                    st.session_state.current_screen = 'calendar'
                    st.session_state.selected_meeting_id = selected_row['id']
                    st.session_state.selected_meeting_title = selected_row['meeting_title']
                    st.session_state.selected_start_date = selected_row['meeting_start_date']
                    st.rerun()
            
            with col2:
                # Weitere Aktionen
                if st.button("🔄 Details aktualisieren"):
                    st.rerun()
            
            with col3:
                st.write("")  # Spacer
    else:
        st.warning("Keine Transkriptionen mit den gewählten Filtern gefunden.")

def start_workflow():
    """Startet den Transcription Workflow."""
    with st.spinner("Starte Transcription Workflow..."):
        result = n8n_client.start_transcription_workflow()
        
        if result["success"]:
            st.success(result["message"])
        else:
            st.error(result["message"])



 