import re
from .db import get_db_connection

def sync_recipient_names():
    conn = get_db_connection()
    cur = conn.cursor()
    # 1. Daten aus calendar_data holen
    cur.execute("SELECT sender_name, display_to, display_cc FROM calendar_data")
    rows = cur.fetchall()
    tokens = set()
    for sender_name, display_to, display_cc in rows:
        for field in [sender_name, display_to, display_cc]:
            if not field:
                continue
            # Split an ; und ,
            parts = re.split(r"[;,]", field)
            for part in parts:
                # Zerlege in Wörter
                words = part.strip().split()
                for word in words:
                    # Filtere leere Tokens und Sonderzeichen
                    clean = re.sub(r"[^\wäöüÄÖÜß-]", "", word)
                    if clean:
                        tokens.add(clean)
    # 2. Schreibe deduplizierte Tokens in recipient_names
    for token in tokens:
        try:
            cur.execute("INSERT INTO recipient_names(token) VALUES (%s) ON CONFLICT DO NOTHING", (token,))
        except Exception:
            pass
    conn.commit()
    cur.close()
    conn.close() 