import re

def tokenize_transcript(transcript):
    # Tokenisiere in Wörter und Satzzeichen
    tokens = re.findall(r"\w+|[.,;:!?]", transcript, re.UNICODE)
    return tokens

def replace_tokens(transcript, matches):
    # Ersetze erkannte Begriffe im Transkript
    for match in matches:
        original = match['original']
        corrected = match['corrected']
        # Nur ganzes Wort ersetzen
        transcript = re.sub(rf'\b{re.escape(original)}\b', corrected, transcript)
    return transcript 