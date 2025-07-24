"""
Screen 2: Kalenderauswahl mit gefilterter AG-Grid.
"""
import streamlit as st
import pandas as pd
from streamlit_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import time # Added missing import for time.sleep

from database import db_manager
from utils.db_utils import prepare_calendar_data

logger = logging.getLogger(__name__)

def render_calendar_screen():
    """Rendert den Kalenderauswahl Screen."""
    
    # Header mit Meeting-Informationen
    meeting_title = st.session_state.get('selected_meeting_title', 'Unbekanntes Meeting')
    start_date = st.session_state.get('selected_start_date', 'Unbekanntes Datum')
    
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="color: #1f77b4; font-family: 'Roboto', sans-serif; font-size: 2rem; font-weight: bold;">
            📅 KALENDER AUSWAHL
        </h1>
        <div style="background-color: #f0f2f6; padding: 1rem; border-radius: 8px; margin: 1rem 0;">
            <p style="margin: 0; font-size: 1.1rem;">
                <strong>Meeting:</strong> {meeting_title} | 
                <strong>Datum:</strong> {start_date}
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Back Button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("← Zurück zu Transkriptionen", use_container_width=True, type="secondary"):
            st.session_state.current_screen = 'transcriptions'
            st.rerun()
    
    with col2:
        st.write("")  # Spacer
    
    with col3:
        st.write("")  # Spacer
    
    # Lade Kalenderdaten für das ausgewählte Datum
    if start_date and start_date != 'Unbekanntes Datum':
        try:
            # Konvertiere Datum für Datenbankabfrage
            if isinstance(start_date, str):
                # Versuche verschiedene Datumsformate
                date_formats = ['%Y-%m-%d %H:%M', '%Y-%m-%d', '%d.%m.%Y']
                parsed_date = None
                
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(start_date, fmt)
                        break
                    except ValueError:
                        continue
                
                if parsed_date:
                    db_date = parsed_date.strftime('%Y-%m-%d')
                else:
                    st.error("Ungültiges Datumsformat")
                    return
            else:
                db_date = start_date.strftime('%Y-%m-%d')
            
            # Lade Kalenderdaten
            with st.spinner("Lade Kalenderdaten..."):
                calendar_data = db_manager.get_calendar_data_by_date(db_date)
            
            if not calendar_data:
                st.warning(f"Keine Kalenderdaten für {db_date} gefunden.")
                return
            
            # Bereite Daten für AG-Grid vor
            df = prepare_calendar_data(calendar_data)
            
            if df.empty:
                st.warning("Keine Daten zum Anzeigen verfügbar.")
                return
            
            # AG-Grid Konfiguration
            gb = GridOptionsBuilder.from_dataframe(df)
            
            # Konfiguriere Spalten
            gb.configure_column("subject", header_name="Betreff", width=400)
            gb.configure_column("start_date", header_name="Start Datum", width=200)
            
            # Select Button
            gb.configure_column(
                "Select",
                header_name="Aktionen",
                cellRenderer="buttonRenderer",
                cellRendererParams={
                    "buttonText": "Auswählen",
                    "style": {"backgroundColor": "#ff7f0e", "color": "white", "border": "none", "padding": "8px 16px", "borderRadius": "4px"}
                },
                width=120
            )
            
            # Grid-Optionen
            gb.configure_grid_options(
                domLayout='normal',
                rowHeight=50,
                pagination=True,
                paginationPageSize=10,
                suppressRowClickSelection=True,
                enableRangeSelection=True,
                enableRangeHandle=True
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
                height=400,
                allow_unsafe_jscode=True,
                custom_css={
                    ".ag-row-hover": {"background-color": "#f0f2f6 !important"},
                    ".ag-header-cell": {"background-color": "#ff7f0e !important", "color": "white !important"},
                    ".ag-header-cell-label": {"color": "white !important"}
                }
            )
            
            # Behandle Button-Clicks
            if grid_response['clicked']:
                handle_calendar_selection(grid_response['clicked'])
                
        except Exception as e:
            logger.error(f"Fehler beim Laden der Kalenderdaten: {e}")
            st.error("Fehler beim Laden der Kalenderdaten")
    else:
        st.error("Kein gültiges Datum für die Kalenderauswahl verfügbar.")

def handle_calendar_selection(clicked_data: Dict[str, Any]):
    """Behandelt die Auswahl eines Kalendereintrags."""
    try:
        if clicked_data and 'row' in clicked_data:
            row_data = clicked_data['row']
            subject = row_data.get('subject', '')
            start_date = row_data.get('start_date', '')
            transcription_id = st.session_state.get('selected_meeting_id')
            
            if transcription_id:
                # Update Meeting-Daten in der Datenbank
                success = db_manager.update_meeting_data(
                    transcription_id=transcription_id,
                    meeting_title=subject,
                    start_date=start_date,
                    participants=""  # Platzhalter - könnte später erweitert werden
                )
                
                if success:
                    st.success(f"Meeting-Daten erfolgreich aktualisiert: {subject}")
                    
                    # Optional: Automatische Rücknavigation
                    st.info("Zurückleitung zu Transkriptionen in 3 Sekunden...")
                    time.sleep(3)
                    st.session_state.current_screen = 'transcriptions'
                    st.rerun()
                else:
                    st.error("Fehler beim Aktualisieren der Meeting-Daten")
            else:
                st.error("Keine Transkription-ID verfügbar")
                
    except Exception as e:
        logger.error(f"Fehler bei der Kalenderauswahl: {e}")
        st.error("Fehler bei der Verarbeitung der Auswahl") 