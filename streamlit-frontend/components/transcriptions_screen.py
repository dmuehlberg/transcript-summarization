"""
Screen 1: Transkriptionen Dashboard mit AG-Grid.
"""
import streamlit as st
import pandas as pd
from streamlit_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
import logging
from typing import Dict, Any, Optional

from database import db_manager
from utils.workflow_utils import n8n_client
from utils.db_utils import prepare_transcriptions_data, format_duration

logger = logging.getLogger(__name__)

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
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("🔄 Refresh Table", use_container_width=True, type="primary"):
            st.rerun()
    
    with col2:
        if st.button("▶️ Start Transcription Workflow", use_container_width=True, type="secondary"):
            start_workflow()
    
    with col3:
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
    
    # AG-Grid Konfiguration
    gb = GridOptionsBuilder.from_dataframe(df)
    
    # Konfiguriere Spalten
    gb.configure_column("id", header_name="ID", width=80, hide=True)
    gb.configure_column("filename", header_name="Dateiname", width=200)
    gb.configure_column("transcription_status", header_name="Status", width=120)
    gb.configure_column("set_language", header_name="Sprache", width=100, editable=True)
    gb.configure_column("meeting_title", header_name="Meeting Titel", width=250)
    gb.configure_column("meeting_start_date", header_name="Start Datum", width=150)
    gb.configure_column("participants", header_name="Teilnehmer", width=200)
    gb.configure_column("transcription_duration", header_name="Transkription Dauer", width=150)
    gb.configure_column("audio_duration", header_name="Audio Dauer", width=120)
    gb.configure_column("created_at", header_name="Erstellt", width=150)
    gb.configure_column("detected_language", header_name="Erkannte Sprache", width=150)
    
    # Select Meeting Button
    gb.configure_column(
        "Select Meeting",
        header_name="Aktionen",
        cellRenderer="buttonRenderer",
        cellRendererParams={
            "buttonText": "Meeting auswählen",
            "style": {"backgroundColor": "#1f77b4", "color": "white", "border": "none", "padding": "8px 16px", "borderRadius": "4px"}
        },
        width=150
    )
    
    # Grid-Optionen
    gb.configure_grid_options(
        domLayout='normal',
        rowHeight=50,
        pagination=True,
        paginationPageSize=20,
        suppressRowClickSelection=True,
        enableRangeSelection=True,
        enableRangeHandle=True,
        suppressColumnVirtualisation=False,
        suppressRowVirtualisation=False
    )
    
    # Erstelle Grid
    grid_options = gb.build()
    
    # Rendere AG-Grid
    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        fit_columns_on_grid_load=True,
        theme="streamlit",
        height=600,
        allow_unsafe_jscode=True,
        custom_css={
            ".ag-row-hover": {"background-color": "#f0f2f6 !important"},
            ".ag-header-cell": {"background-color": "#1f77b4 !important", "color": "white !important"},
            ".ag-header-cell-label": {"color": "white !important"}
        }
    )
    
    # Behandle Grid-Updates
    if grid_response['changed']:
        handle_grid_updates(grid_response['data'])
    
    # Behandle Button-Clicks
    if grid_response['clicked']:
        handle_button_clicks(grid_response['clicked'])

def start_workflow():
    """Startet den Transcription Workflow."""
    with st.spinner("Starte Transcription Workflow..."):
        result = n8n_client.start_transcription_workflow()
        
        if result["success"]:
            st.success(result["message"])
        else:
            st.error(result["message"])

def handle_grid_updates(updated_data: pd.DataFrame):
    """Behandelt Updates aus der AG-Grid."""
    try:
        # Finde geänderte Zeilen
        for index, row in updated_data.iterrows():
            transcription_id = row['id']
            new_language = row['set_language']
            
            # Update in Datenbank
            success = db_manager.update_transcription_language(transcription_id, new_language)
            
            if success:
                st.success(f"Sprache für Transkription {transcription_id} aktualisiert")
            else:
                st.error(f"Fehler beim Aktualisieren der Sprache für Transkription {transcription_id}")
                
    except Exception as e:
        logger.error(f"Fehler beim Verarbeiten der Grid-Updates: {e}")
        st.error("Fehler beim Aktualisieren der Daten")

def handle_button_clicks(clicked_data: Dict[str, Any]):
    """Behandelt Button-Clicks in der AG-Grid."""
    try:
        if clicked_data and 'row' in clicked_data:
            row_data = clicked_data['row']
            transcription_id = row_data['id']
            meeting_title = row_data.get('meeting_title', '')
            meeting_start_date = row_data.get('meeting_start_date', '')
            
            # Navigiere zu Calendar Screen
            st.session_state.current_screen = 'calendar'
            st.session_state.selected_meeting_id = transcription_id
            st.session_state.selected_meeting_title = meeting_title
            st.session_state.selected_start_date = meeting_start_date
            
            st.rerun()
            
    except Exception as e:
        logger.error(f"Fehler beim Verarbeiten der Button-Clicks: {e}")
        st.error("Fehler beim Verarbeiten der Aktion") 