"""
Screen 1: Transkriptionen Dashboard mit nativen Streamlit-Komponenten.
"""
import streamlit as st
import pandas as pd
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
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col1:
        if st.button("🔄 Refresh Table", use_container_width=True, type="primary"):
            st.rerun()
    
    with col2:
        if st.button("▶️ Start Transcription Workflow", use_container_width=True, type="secondary"):
            start_workflow()
    
    with col3:
        if st.button("🗑️ Markierte löschen", use_container_width=True, type="secondary"):
            delete_selected_transcriptions()
    
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
    
    # Erstelle eine interaktive Tabelle mit nativen Streamlit-Komponenten
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
        # Erstelle eine erweiterte DataFrame mit Checkbox-Spalte
        display_df = filtered_df[['filename', 'transcription_status', 'set_language', 'meeting_title', 'meeting_start_date']].copy()
        
        # Füge eine Checkbox-Spalte hinzu
        st.subheader("📊 Transkriptionen Tabelle")
        
        # Erstelle eine interaktive Tabelle mit Checkboxen
        col1, col2 = st.columns([0.8, 0.2])
        
        with col1:
            # Zeige die Haupttabelle
            st.dataframe(
                display_df,
                use_container_width=True,
                height=400
            )
        
        with col2:
            # Zeige Checkboxen für jede Zeile
            st.write("**Auswahl:**")
            selected_count = 0
            for idx, row in filtered_df.iterrows():
                transcription_id = row['id']
                checkbox_key = f"checkbox_{transcription_id}"
                if st.checkbox(
                    f"ID: {transcription_id}",
                    key=checkbox_key,
                    help=f"{row['filename']} - {row['meeting_title']}"
                ):
                    selected_count += 1
            
            if selected_count > 0:
                st.success(f"✅ {selected_count} ausgewählt")
            else:
                st.info("Keine ausgewählt")
        
        # Zeige Details für ausgewählte Zeile
        st.subheader("📝 Details")
        selected_index = st.selectbox(
            "Wähle eine Transkription für Details:",
            range(len(filtered_df)),
            format_func=lambda x: f"{filtered_df.iloc[x]['filename']} - {filtered_df.iloc[x]['meeting_title']}"
        )
        
        if selected_index is not None:
            selected_row = filtered_df.iloc[selected_index]
            
            # Details in Spalten anzeigen
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Dateiname:**", selected_row['filename'])
                st.write("**Status:**", selected_row['transcription_status'])
                st.write("**Sprache:**", selected_row['set_language'])
                st.write("**Meeting Titel:**", selected_row['meeting_title'])
            
            with col2:
                st.write("**Start Datum:**", selected_row['meeting_start_date'])
                st.write("**Teilnehmer:**", selected_row.get('participants', 'N/A'))
                st.write("**Audio Dauer:**", format_duration(selected_row.get('audio_duration')))
                st.write("**Erstellt:**", selected_row.get('created_at', 'N/A'))
            
            # Aktionen
            st.subheader("⚡ Aktionen")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Sprache bearbeiten
                new_language = st.selectbox(
                    "Sprache ändern:",
                    ["de", "en", "fr", "es", "it"],
                    index=["de", "en", "fr", "es", "it"].index(selected_row['set_language']) if selected_row['set_language'] in ["de", "en", "fr", "es", "it"] else 0
                )
                if st.button("💾 Sprache speichern"):
                    if db_manager and db_manager.update_transcription_language(selected_row['id'], new_language):
                        st.success("Sprache erfolgreich aktualisiert!")
                        st.rerun()
                    else:
                        st.error("Fehler beim Aktualisieren der Sprache")
            
            with col2:
                # Meeting auswählen
                if st.button("📅 Meeting auswählen"):
                    st.session_state.current_screen = 'calendar'
                    st.session_state.selected_meeting_id = selected_row['id']
                    st.session_state.selected_meeting_title = selected_row['meeting_title']
                    st.session_state.selected_start_date = selected_row['meeting_start_date']
                    st.rerun()
            
            with col3:
                # Weitere Aktionen
                if st.button("🔄 Details aktualisieren"):
                    st.rerun()
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

def delete_selected_transcriptions():
    """Löscht die ausgewählten Transkriptionen."""
    # Sammle alle ausgewählten IDs
    selected_ids = []
    
    # Debug: Zeige alle Session State Keys
    st.write("Debug - Session State Keys:", list(st.session_state.keys()))
    
    for key in st.session_state:
        if key.startswith("checkbox_") and st.session_state[key]:
            # Extrahiere ID aus dem Key (checkbox_123 -> 123)
            try:
                transcription_id = int(key.replace("checkbox_", ""))
                selected_ids.append(transcription_id)
                st.write(f"Debug - Gefunden: {key} = {transcription_id}")
            except ValueError:
                st.write(f"Debug - Ungültige ID in Key: {key}")
    
    st.write(f"Debug - Ausgewählte IDs: {selected_ids}")
    
    if not selected_ids:
        st.warning("Keine Transkriptionen zum Löschen ausgewählt.")
        return
    
    # Bestätigungsdialog
    st.warning(f"⚠️ Möchten Sie wirklich {len(selected_ids)} Transkription(en) löschen?")
    st.write(f"Zu löschende IDs: {selected_ids}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("❌ Abbrechen", use_container_width=True):
            st.rerun()
    
    with col2:
        if st.button("🗑️ Endgültig löschen", use_container_width=True, type="primary"):
            with st.spinner("Lösche Transkriptionen..."):
                if db_manager and db_manager.delete_transcriptions(selected_ids):
                    st.success(f"✅ {len(selected_ids)} Transkription(en) erfolgreich gelöscht!")
                    
                    # Lösche Checkbox-States
                    for transcription_id in selected_ids:
                        checkbox_key = f"checkbox_{transcription_id}"
                        if checkbox_key in st.session_state:
                            del st.session_state[checkbox_key]
                    
                    st.rerun()
                else:
                    st.error("❌ Fehler beim Löschen der Transkriptionen")

 