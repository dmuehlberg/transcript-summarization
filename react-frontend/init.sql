-- Transkriptions-Tabelle
CREATE TABLE IF NOT EXISTS transcriptions (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    transcription_status VARCHAR(50) DEFAULT 'pending',
    set_language VARCHAR(10) DEFAULT 'auto',
    meeting_title TEXT,
    meeting_start_date TIMESTAMP,
    participants TEXT,
    transcription_duration INTEGER,
    audio_duration INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    detected_language VARCHAR(10),
    transcript_text TEXT,
    corrected_text TEXT,
    recording_date TIMESTAMP
);

-- Kalender-Einträge Tabelle
CREATE TABLE IF NOT EXISTS calendar_entries (
    id SERIAL PRIMARY KEY,
    subject VARCHAR(255) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    location TEXT,
    attendees TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Spaltenkonfiguration für React-Tabellen
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

-- Indizes für bessere Performance
CREATE INDEX IF NOT EXISTS idx_transcriptions_status ON transcriptions(transcription_status);
CREATE INDEX IF NOT EXISTS idx_transcriptions_language ON transcriptions(set_language);
CREATE INDEX IF NOT EXISTS idx_transcriptions_created_at ON transcriptions(created_at);
CREATE INDEX IF NOT EXISTS idx_calendar_start_date ON calendar_entries(start_date);
CREATE INDEX IF NOT EXISTS idx_react_table_column_config_table ON react_table_column_config(table_name);
CREATE INDEX IF NOT EXISTS idx_react_table_column_config_order ON react_table_column_config(table_name, column_order);

-- Standard-Spaltenkonfiguration für Transkriptions-Tabelle
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

-- Beispieldaten für Tests
INSERT INTO transcriptions (filename, transcription_status, set_language, meeting_title, meeting_start_date, participants, transcription_duration, audio_duration, detected_language, transcript_text, recording_date) VALUES
('meeting_2024_01_15.mp3', 'completed', 'de', 'Wöchentliches Team-Meeting', '2024-01-15 10:00:00', 'Max Mustermann, Anna Schmidt, Peter Müller', 1800, 1800, 'de', 'Guten Morgen alle zusammen. Heute besprechen wir die aktuellen Projekte...', '2024-01-15 10:00:00'),
('client_call_2024_01_16.mp3', 'processing', 'en', 'Kundengespräch Projekt Alpha', '2024-01-16 14:30:00', 'John Doe, Jane Smith', 900, 900, 'en', 'Hello, thank you for joining us today...', '2024-01-16 14:30:00'),
('review_2024_01_17.mp3', 'pending', 'auto', 'Code Review Session', '2024-01-17 16:00:00', 'Developer Team', NULL, 1200, NULL, NULL, '2024-01-17 16:00:00')
ON CONFLICT DO NOTHING;

INSERT INTO calendar_entries (subject, start_date, end_date, location, attendees) VALUES
('Wöchentliches Team-Meeting', '2024-01-15 10:00:00', '2024-01-15 11:00:00', 'Konferenzraum A', 'Max Mustermann, Anna Schmidt, Peter Müller'),
('Kundengespräch Projekt Alpha', '2024-01-16 14:30:00', '2024-01-16 15:30:00', 'Online - Zoom', 'John Doe, Jane Smith'),
('Code Review Session', '2024-01-17 16:00:00', '2024-01-17 17:00:00', 'Entwickler-Büro', 'Developer Team'),
('Projektplanung Q1', '2024-01-18 09:00:00', '2024-01-18 12:00:00', 'Meeting Room B', 'Management Team')
ON CONFLICT DO NOTHING; 