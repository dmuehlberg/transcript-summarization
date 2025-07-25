"""
Hauptanwendung für das Streamlit Transcription Dashboard.
"""
import streamlit as st
import logging
from dotenv import load_dotenv
import os

# Importe
from database import db_manager
from components.transcriptions_screen import render_transcriptions_screen
from components.calendar_screen import render_calendar_screen

# Lade Umgebungsvariablen
load_dotenv()

# Logger konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_page_config():
    """Konfiguriert die Streamlit-Seite."""
    st.set_page_config(
        page_title="Transcription Dashboard",
        page_icon="📝",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

def setup_custom_css():
    """Fügt benutzerdefiniertes CSS hinzu."""
    st.markdown("""
    <style>
    /* Hauptfarben */
    .main-header {
        color: #1f77b4;
        font-family: 'Roboto', sans-serif;
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* Button-Styling */
    .stButton > button {
        font-family: 'Roboto', sans-serif;
        font-weight: 500;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    
    /* Container-Styling */
    .main-container {
        background-color: #f0f2f6;
        padding: 2rem;
        border-radius: 12px;
        margin: 1rem 0;
    }
    
    /* Status-Badges */
    .status-completed {
        background-color: #28a745;
        color: white;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    
    .status-processing {
        background-color: #ffc107;
        color: black;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    
    .status-failed {
        background-color: #dc3545;
        color: white;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    
    /* Loading-Spinner */
    .stSpinner > div {
        border-color: #1f77b4 !important;
    }
    
    /* Error-Messages */
    .stAlert {
        border-radius: 8px;
        border: none;
    }
    
    /* Success-Messages */
    .stSuccess {
        background-color: #d4edda;
        border-color: #c3e6cb;
        color: #155724;
    }
    
    /* Warning-Messages */
    .stWarning {
        background-color: #fff3cd;
        border-color: #ffeaa7;
        color: #856404;
    }
    
    /* Error-Messages */
    .stError {
        background-color: #f8d7da;
        border-color: #f5c6cb;
        color: #721c24;
    }
    </style>
    """, unsafe_allow_html=True)

def initialize_session_state():
    """Initialisiert den Session State."""
    if 'current_screen' not in st.session_state:
        st.session_state.current_screen = 'transcriptions'
    
    if 'selected_meeting_id' not in st.session_state:
        st.session_state.selected_meeting_id = None
    
    if 'selected_meeting_title' not in st.session_state:
        st.session_state.selected_meeting_title = None
    
    if 'selected_start_date' not in st.session_state:
        st.session_state.selected_start_date = None

def check_database_connection():
    """Überprüft die Datenbankverbindung."""
    try:
        if not db_manager.test_connection():
            st.error("❌ Keine Verbindung zur Datenbank möglich. Bitte überprüfen Sie die Konfiguration.")
            st.stop()
        else:
            st.success("✅ Datenbankverbindung erfolgreich")
    except Exception as e:
        st.error(f"❌ Datenbankfehler: {e}")
        st.stop()

def render_navigation():
    """Rendert die Navigation zwischen Screens."""
    # Navigation nur anzeigen, wenn wir nicht auf dem Hauptscreen sind
    if st.session_state.current_screen != 'transcriptions':
        st.sidebar.markdown("### Navigation")
        if st.sidebar.button("🏠 Zurück zum Dashboard"):
            st.session_state.current_screen = 'transcriptions'
            st.rerun()

def main():
    """Hauptfunktion der Anwendung."""
    try:
        # Setup
        setup_page_config()
        setup_custom_css()
        initialize_session_state()
        
        # Header
        st.markdown("""
        <div style="text-align: center; margin-bottom: 1rem;">
            <h1 style="color: #1f77b4; font-family: 'Roboto', sans-serif; font-size: 2.5rem; font-weight: bold;">
                Transcription Service Dashboard
            </h1>
            <p style="color: #666; font-size: 1.1rem;">
                Moderne Steuerung für Transkriptions-Workflows
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Datenbankverbindung testen
        with st.expander("🔧 System-Status", expanded=False):
            check_database_connection()
        
        # Navigation
        render_navigation()
        
        # Screen-Rendering basierend auf Session State
        if st.session_state.current_screen == 'transcriptions':
            render_transcriptions_screen()
        elif st.session_state.current_screen == 'calendar':
            render_calendar_screen()
        else:
            st.error("Unbekannter Screen")
            st.session_state.current_screen = 'transcriptions'
            st.rerun()
        
        # Footer
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; color: #666; font-size: 0.9rem;">
            <p>Transcription Service Dashboard v1.0 | Powered by Streamlit & AG-Grid</p>
        </div>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        logger.error(f"Kritischer Fehler in der Hauptanwendung: {e}")
        st.error(f"Ein kritischer Fehler ist aufgetreten: {e}")
        st.info("Bitte laden Sie die Seite neu oder kontaktieren Sie den Administrator.")

if __name__ == "__main__":
    main() 