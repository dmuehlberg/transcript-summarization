from .db import get_db_connection
import cologne_phonetics
import jellyfish
from rapidfuzz import fuzz, process


def match_tokens(tokens, language, options):
    conn = get_db_connection()
    cur = conn.cursor()
    # Referenzlisten holen
    cur.execute("SELECT token FROM recipient_names")
    recipient_names = [row[0] for row in cur.fetchall()]
    manual_terms = []
    if options.get('include_manual_list'):
        cur.execute("SELECT term FROM manual_terms")
        manual_terms = [row[0] for row in cur.fetchall()]
    reference = recipient_names + manual_terms
    matches = []
    for token in tokens:
        best_match = None
        best_score = 0
        match_type = None
        source = None
        # Phonetisches Matching
        if language == 'de':
            token_phon = cologne_phonetics.encode(token)[0][1]
            for ref in reference:
                ref_phon = cologne_phonetics.encode(ref)[0][1]
                if token_phon == ref_phon:
                    best_match = ref
                    match_type = 'phonetic'
                    source = 'recipient_names' if ref in recipient_names else 'manual_terms'
                    break
        elif language == 'en':
            token_phon = jellyfish.metaphone(token)
            for ref in reference:
                ref_phon = jellyfish.metaphone(ref)
                if token_phon == ref_phon:
                    best_match = ref
                    match_type = 'phonetic'
                    source = 'recipient_names' if ref in recipient_names else 'manual_terms'
                    break
        # Fuzzy Matching (optional)
        if not best_match and options.get('min_score'):
            result = process.extractOne(token, reference, scorer=fuzz.ratio)
            if result and result[1] >= options['min_score']:
                best_match = result[0]
                best_score = result[1]
                match_type = 'fuzzy'
                source = 'recipient_names' if best_match in recipient_names else 'manual_terms'
        if best_match:
            matches.append({
                'original': token,
                'corrected': best_match,
                'match_type': match_type,
                'score': best_score if match_type == 'fuzzy' else None,
                'source': source
            })
    cur.close()
    conn.close()
    return matches 