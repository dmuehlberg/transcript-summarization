# Platzhalter für Datenmodelle

class CorrectionMatch:
    def __init__(self, original, corrected, match_type, score, source):
        self.original = original
        self.corrected = corrected
        self.match_type = match_type
        self.score = score
        self.source = source 