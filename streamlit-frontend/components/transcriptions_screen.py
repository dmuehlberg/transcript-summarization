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
    try:
        if edited_df is not None and original_df is not None:
            if len(edited_df) > 0 and len(original_df) > 0:
                # Sichere DataFrame-Vergleich
                try:
                    is_equal = edited_df.equals(original_df)
                    if not is_equal:
                        # Finde geänderte Zeilen
                        for index, row in edited_df.iterrows():
                            if index in original_df.index:
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
                except Exception as compare_error:
                    st.warning(f"Fehler beim Vergleich in handle_cell_edit: {str(compare_error)}")
                    return original_df
        return original_df
    except Exception as e:
        st.error(f"❌ Fehler beim Bearbeiten der Zellen: {str(e)}")
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
            # Setze Refresh-Flag und lösche cached Daten
            st.session_state.refresh_data = True
            if 'previous_df' in st.session_state:
                del st.session_state.previous_df
            st.rerun()
    
    with col2:
        if st.button("▶️ Start Transcription Workflow", use_container_width=True, type="secondary"):
            start_workflow()
    
    with col3:
        if st.button("🗑️ Markierte löschen", use_container_width=True, type="secondary"):
            # Sammle alle ausgewählten IDs aus AG Grid
            selected_ids = []
            
            # Extrahiere selected_rows aus dem Session State oder Grid Response
            if 'selected_rows' in st.session_state and st.session_state.selected_rows is not None:
                selected_rows = st.session_state.selected_rows
                
                # Behandle DataFrame vs Liste
                if hasattr(selected_rows, 'iloc'):
                    # selected_rows ist ein DataFrame
                    for index, row in selected_rows.iterrows():
                        if 'id' in row:
                            selected_ids.append(row['id'])
                else:
                    # selected_rows ist eine Liste von Dictionaries
                    for row in selected_rows:
                        if 'id' in row:
                            selected_ids.append(row['id'])
            
            if not selected_ids:
                st.warning("Keine Transkriptionen zum Löschen ausgewählt.")
            else:
                # Führe Delete direkt aus
                try:
                    if db_manager:
                        result = db_manager.delete_transcriptions(selected_ids)
                        
                        if result:
                            st.success(f"✅ {len(selected_ids)} Transkription(en) erfolgreich gelöscht!")
                            
                            # Lösche selected_rows aus Session State
                            if 'selected_rows' in st.session_state:
                                del st.session_state.selected_rows
                            
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
    
    # Reset Refresh-Flag nach dem Laden
    if 'refresh_data' in st.session_state:
        del st.session_state.refresh_data
    
    if transcriptions is None or len(transcriptions) == 0:
        st.warning("Keine Transkriptionen gefunden.")
        return
    
    # Bereite Daten für AG-Grid vor
    try:
        df = prepare_transcriptions_data(transcriptions)
        
        if df is None or len(df) == 0:
            st.warning("Keine Daten zum Anzeigen verfügbar.")
            return
    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {str(e)}")
        return
    
    # Erstelle eine interaktive Tabelle mit AG Grid
    st.subheader("📊 Transkriptionen Tabelle")
    
    # Filter-Optionen
    col1, col2, col3 = st.columns(3)
    with col1:
        # Sichere Status-Filter-Optionen
        status_options = ["Alle"]
        if 'transcription_status' in df.columns:
            try:
                status_options.extend(list(df['transcription_status'].unique()))
            except Exception as e:
                st.error(f"Fehler beim Laden der Status-Optionen: {str(e)}")
        
        status_filter = st.selectbox("Status Filter", status_options)
    
    with col2:
        # Sichere Language-Filter-Optionen
        language_options = ["Alle"]
        if 'set_language' in df.columns:
            try:
                language_options.extend(list(df['set_language'].unique()))
            except Exception as e:
                st.error(f"Fehler beim Laden der Sprach-Optionen: {str(e)}")
        
        language_filter = st.selectbox("Sprache Filter", language_options)
    
    with col3:
        search_term = st.text_input("🔍 Suche", placeholder="Dateiname oder Meeting-Titel...")
    
    # Filtere Daten
    filtered_df = df.copy()
    
    # Status Filter
    if status_filter != "Alle" and 'transcription_status' in filtered_df.columns:
        status_mask = filtered_df['transcription_status'] == status_filter
        filtered_df = filtered_df[status_mask]
    
    # Language Filter
    if language_filter != "Alle" and 'set_language' in filtered_df.columns:
        language_mask = filtered_df['set_language'] == language_filter
        filtered_df = filtered_df[language_mask]
    
    # Search Filter
    if search_term and len(search_term.strip()) > 0:
        try:
            filename_mask = filtered_df['filename'].str.contains(search_term, case=False, na=False)
            title_mask = filtered_df['meeting_title'].str.contains(search_term, case=False, na=False)
            search_mask = filename_mask | title_mask
            filtered_df = filtered_df[search_mask]
        except Exception as e:
            st.error(f"Fehler beim Filtern: {str(e)}")
    
    # Zeige gefilterte Daten
    if filtered_df is not None and len(filtered_df) > 0:
        # AG Grid Konfiguration
        try:
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
                    'values': ['auto', 'de', 'en']
                },
                width=100
            )
            
            # Konfiguriere Checkbox-Spalte als erste Spalte
            gb.configure_column(
                "id", 
                header_name="", 
                width=50, 
                checkboxSelection=False,  # Keine Checkboxen in der Spalte
                headerCheckboxSelection=False,
                pinned='left'
            )
            
            # Konfiguriere andere Spalten
            gb.configure_column("filename", header_name="Dateiname", width=200)
            gb.configure_column("transcription_status", header_name="Status", width=120)
            gb.configure_column("meeting_title", header_name="Meeting Titel", width=250)
            gb.configure_column("meeting_start_date", header_name="Start Datum", width=150)
            
            # Aktiviere Row Selection mit Checkboxen
            gb.configure_selection(
                selection_mode='multiple', 
                use_checkbox=True,  # Checkboxen aktivieren
                pre_selected_rows=[],
                suppressRowClickSelection=False,
                groupSelectsChildren=True
            )
            
            grid_options = gb.build()
            
            # Explizit Checkbox-Konfiguration hinzufügen
            grid_options['rowSelection'] = 'multiple'
            grid_options['suppressRowClickSelection'] = False
            grid_options['checkboxSelection'] = True
            grid_options['suppressRowDeselection'] = False
            grid_options['suppressHeaderMenuHide'] = True
            grid_options['suppressMenuHide'] = True
            
        except Exception as e:
            st.error(f"Fehler bei AG Grid Konfiguration: {str(e)}")
            return
        
        # Zeige AG Grid
        try:
            # Wähle nur die benötigten Spalten (ID bleibt sichtbar für Checkboxen)
            display_columns = ['id', 'filename', 'transcription_status', 'set_language', 'meeting_title', 'meeting_start_date']
            display_df = filtered_df[display_columns].copy()
            
            grid_response = AgGrid(
                display_df,
                gridOptions=grid_options,
                data_return_mode=DataReturnMode.AS_INPUT,
                update_mode=GridUpdateMode.SELECTION_CHANGED,  # Ändern zu SELECTION_CHANGED für bessere Reaktion
                fit_columns_on_grid_load=True,
                theme='streamlit',
                height=400,
                allow_unsafe_jscode=True,
                custom_css={
                    ".ag-row-hover": {"background-color": "lightblue !important"},
                    ".ag-row-selected": {"background-color": "#e6f3ff !important"},
                    ".ag-checkbox-input": {"display": "block !important"},
                    ".ag-checkbox": {"display": "block !important"},
                    ".ag-header-select-all": {"display": "none !important"},
                    ".ag-header-checkbox": {"display": "none !important"},
                    ".ag-header-cell .ag-checkbox": {"display": "none !important"}
                },
                custom_js_code="""
                // Erzwinge Checkbox-Anzeige
                setTimeout(function() {
                    var gridDiv = document.querySelector('.ag-root-wrapper');
                    if (gridDiv) {
                        var checkboxes = gridDiv.querySelectorAll('.ag-checkbox-input');
                        checkboxes.forEach(function(checkbox) {
                            checkbox.style.display = 'block';
                            checkbox.style.visibility = 'visible';
                        });
                    }
                }, 100);
                """
            )
        except Exception as e:
            st.error(f"Fehler beim Anzeigen der AG Grid: {str(e)}")
            return
        
        # Behandle Zellenänderungen
        if 'previous_df' not in st.session_state:
            st.session_state.previous_df = filtered_df[['id', 'filename', 'transcription_status', 'set_language', 'meeting_title', 'meeting_start_date']].copy()
        
        # Extrahiere Daten und ausgewählte Zeilen
        current_df = None
        selected_rows = []
        
        try:
            # Extrahiere Daten aus AgGridReturn Objekt
            if hasattr(grid_response, 'data'):
                current_df = pd.DataFrame(grid_response.data) if grid_response.data is not None else None
            
            # Extrahiere selected_rows aus AgGridReturn Objekt
            if hasattr(grid_response, 'selected_rows'):
                selected_rows = grid_response.selected_rows if grid_response.selected_rows is not None else []
                # Speichere selected_rows im Session State für andere Funktionen
                st.session_state.selected_rows = selected_rows
            else:
                selected_rows = []
                st.session_state.selected_rows = []
                
        except Exception as e:
            st.error(f"Fehler beim Extrahieren der Grid-Daten: {str(e)}")
            return
        
        # Behandle Zellenänderungen
        if current_df is not None and len(current_df) > 0:
            if 'previous_df' in st.session_state and st.session_state.previous_df is not None:
                # Sichere DataFrame-Vergleich
                try:
                    is_equal = current_df.equals(st.session_state.previous_df)
                    if not is_equal:
                        updated_df = handle_cell_edit(current_df, st.session_state.previous_df)
                        if updated_df is not None:
                            st.session_state.previous_df = updated_df.copy()
                except Exception as compare_error:
                    st.warning(f"Fehler beim Vergleich der Daten: {str(compare_error)}")
                    st.session_state.previous_df = current_df.copy()
            else:
                st.session_state.previous_df = current_df.copy()
        
        # Zeige Details für ausgewählte Zeile
        if selected_rows is not None and hasattr(selected_rows, '__len__') and len(selected_rows) > 0:
            st.subheader(f"📝 Details ({len(selected_rows)} ausgewählt)")
            
            try:
                # Zeige Details der ersten ausgewählten Zeile
                if hasattr(selected_rows, 'iloc'):
                    # selected_rows ist ein DataFrame
                    selected_row = selected_rows.iloc[0].to_dict()
                else:
                    # selected_rows ist eine Liste von Dictionaries
                    selected_row = selected_rows[0]
                
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
                    try:
                        matching_rows = filtered_df[filtered_df['id'] == selected_row['id']]
                        
                        if len(matching_rows) > 0:
                            original_row = matching_rows.iloc[0]
                            st.write("**Teilnehmer:**", original_row.get('participants', 'N/A'))
                            st.write("**Audio Dauer:**", format_duration(original_row.get('audio_duration')))
                            st.write("**Erstellt:**", original_row.get('created_at', 'N/A'))
                    except Exception as e:
                        st.error(f"Fehler beim Laden zusätzlicher Details: {str(e)}")
                
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
                
            except Exception as e:
                st.error(f"Fehler beim Anzeigen der Details: {str(e)}")
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



 