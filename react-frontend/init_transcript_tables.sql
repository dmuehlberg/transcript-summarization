-- Transkriptions-Tabellen für die React-App
-- Diese Tabellen werden in die bestehende n8n-Datenbank eingefügt

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

-- Indizes für bessere Performance
CREATE INDEX IF NOT EXISTS idx_transcriptions_status ON transcriptions(transcription_status);
CREATE INDEX IF NOT EXISTS idx_transcriptions_language ON transcriptions(set_language);
CREATE INDEX IF NOT EXISTS idx_transcriptions_created_at ON transcriptions(created_at);
CREATE INDEX IF NOT EXISTS idx_calendar_start_date ON calendar_entries(start_date);

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