import datetime, struct, pypff, re

# ---------------------------------
# pypff-Kompatibilitäts-Helpers
# ---------------------------------

def _folder_count_msgs(folder) -> int:
    """
    Liefert die Anzahl der Nachrichten in einem Folder, egal wie das Attribut heißt.
    """
    for attr in ("number_of_messages",             # neuere Bindings
                 "number_of_items",                # manche Builds
                 "number_of_sub_messages"):        # ältere Bindings
        if hasattr(folder, attr):
            return getattr(folder, attr)

    if hasattr(folder, "get_number_of_messages"):  # Fallback als Methode
        return folder.get_number_of_messages()

    return 0


def _folder_count_subfolders(folder) -> int:
    for attr in ("number_of_sub_folders",
                 "number_of_subfolders"):
        if hasattr(folder, attr):
            return getattr(folder, attr)

    if hasattr(folder, "get_number_of_sub_folders"):
        return folder.get_number_of_sub_folders()

    return 0


def _folder_get_subfolder(folder, index):
    for fn in ("get_sub_folder", "get_subfolder"):
        if hasattr(folder, fn):
            return getattr(folder, fn)(index)


def _folder_get_message(folder, index):
    for fn in ("get_message", "get_sub_message"):
        if hasattr(folder, fn):
            return getattr(folder, fn)(index)

def extract_attendees(ost_path):
    attendees = []
    pst_file = pypff.file()
    pst_file.open(ost_path)

    for folder in pst_file.get_root_folder().sub_folders:
        if "calendar" in folder.name.lower():
            for msg in folder.sub_messages:
                subject = msg.subject
                organizer = msg.sender_name
                required = msg.get_value_string(0x0003)  # Beispiel
                attendees.append({
                    "subject": subject,
                    "organizer": organizer,
                    "required": required
                })

    pst_file.close()
    return attendees

def extract_calendar_entries(pst_path: str):
    pst = pypff.file(); pst.open(pst_path)
    entries = []

    # relevante Property-Tags
    TAGS = [(0x0060, 0x0061),  # PR_START_DATE / PR_END_DATE
            (0x820d, 0x820e)]  # PidLidAppointmentStartWhole / EndWhole

    def walk(folder):
        for msg in folder.sub_messages:
            if (msg.message_class or "").upper().startswith("IPM.APPOINTMENT"):
                subject = msg.subject or "(ohne Betreff)"
                start, end = None, None
                for s_tag, e_tag in TAGS:
                    start = start or msg.get_value_datetime(s_tag)
                    end   = end   or msg.get_value_datetime(e_tag)
                start = (start or msg.delivery_time)
                entries.append(
                    {"subject": subject,
                     "start": start.isoformat() if start else None,
                     "end":   end.isoformat()   if end   else None}
                )
        for sub in folder.sub_folders:
            walk(sub)

    walk(pst.get_root_folder())
    pst.close()
    return entries


def list_folders(pst_path: str):
    """
    Gibt eine rekursive Liste aller Ordner mit Item-Anzahl zurück.
    """
    pst = pypff.file(); pst.open(pst_path)
    result = []

    def walk(folder, path=""):
        name = folder.name or "(kein Name)"
        cur  = f"{path}/{name}".lstrip("/")
        result.append({"folder": cur, "messages": folder.number_of_sub_messages})
        for sub in folder.sub_folders:
            walk(sub, cur)

    walk(pst.get_root_folder())
    pst.close()
    return result


def _is_calendar_message(msg) -> bool:
    """Erkennt IPM.Appointment-Nachrichten auch dann, wenn .message_class fehlt."""
    # Variante A – über die Methode (neueres pypff)
    if hasattr(msg, "get_message_class"):
        mclass = (msg.get_message_class() or "").upper()
        if mclass.startswith("IPM.APPOINTMENT"):
            return True
    # Variante B – typische Start/End-Tags vorhanden?
    for tag in (0x0060, 0x820d):             # PR_START_DATE  / PidLidAppointmentStartWhole
        try:
            if msg.get_value_datetime(tag):   # wenn Tag existiert und gültig ist → wohl Termin
                return True
        except IOError:
            continue
    return False

def _get_dt(msg, prop_tag):
    """
    Holt einen DATETIME-Wert, egal welche pypff-Variante:
    gibt datetime.datetime oder None zurück.
    """
    for meth in ("get_value_date_time",
                 "get_value_datetime",
                 "get_value_filetime",
                 "get_value_system_time"):
        if hasattr(msg, meth):
            try:
                return getattr(msg, meth)(prop_tag)
            except IOError:
                pass            # Property existiert nicht
    return None


def extract_all_calendar_entries(pst_path: str):
    """
    Gibt Liste mit Ordnerpfad, Betreff, Start, End zurück.
    Ein Termin ist jede Message in Ordnern mit 'calendar'/'kalender' im Namen.
    """
    pst = pypff.file(); pst.open(pst_path)
    results = []

    TAGS = [(0x0060, 0x0061),   # PR_START_DATE / PR_END_DATE
            (0x820d, 0x820e)]   # PidLidAppointmentStartWhole / EndWhole

    def walk(folder, path=""):
        current = f"{path}/{folder.name or '(kein Name)'}".lstrip("/")

        looks_like_calendar = any(tok in current.lower()
                                   for tok in ("calendar", "kalender"))

        if looks_like_calendar:
            for msg in folder.sub_messages:
                subject = msg.subject or "(kein Betreff)"
                start, end = None, None
                for s_tag, e_tag in TAGS:
                    start = start or _get_dt(msg, s_tag)
                    end   = end   or _get_dt(msg, e_tag)
                start = start or msg.delivery_time  # Fallback

                results.append({
                    "folder": current,
                    "subject": subject,
                    "start": start.isoformat() if isinstance(start, datetime.datetime) else None,
                    "end":   end.isoformat()   if isinstance(end,   datetime.datetime) else None
                })

        for sub in folder.sub_folders:
            walk(sub, current)

    walk(pst.get_root_folder())
    pst.close()
    return sorted(results, key=lambda x: (x["start"] or ""))

_CAL_RE = re.compile(r"(calendar|kalender)", re.I)


def _filetime_to_str(raw: bytes) -> str | None:
    if not raw or len(raw) != 8:
        return None
    ticks, = struct.unpack("<Q", raw)          # little-endian uint64
    dt = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=ticks / 10)
    if 1900 <= dt.year <= 3000:
        return dt.isoformat()
    return None


def _decode(raw: bytes):
    if raw is None:
        return None
    ft = _filetime_to_str(raw)
    if ft:
        return ft
    try:                                   # UTF-8
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:                               # UTF-16-LE
            return raw.decode("utf-16-le")
        except UnicodeDecodeError:
            return f"<{len(raw)} bytes>"


def dump_calendar_properties(pst_path: str, max_items: int = 10):
    pst = pypff.file(); pst.open(pst_path)
    out = []

    def walk(folder, cur=""):
        nonlocal max_items
        if max_items <= 0:
            return

        path = f"{cur}/{folder.name or '(kein Name)'}".lstrip("/")

        # Nur Ordner, deren Name „Kalender“ o. Ä. enthält
        if _CAL_RE.search(path):
            for mi in range(folder.number_of_sub_messages):
                if max_items <= 0:
                    break
                msg = folder.get_sub_message(mi)

                props = {}
                for rs_idx in range(msg.number_of_record_sets):
                    rs = msg.get_record_set(rs_idx)
                    for ent_idx in range(rs.number_of_entries):
                        ent = rs.get_entry(ent_idx)

                        # Identifier robust auslesen
                        if hasattr(ent, "get_identifier"):
                            pid = ent.get_identifier()
                        else:
                            pid = ent.get_entry_type()

                        val = _decode(ent.get_data())
                        if val not in (None, ""):
                            props[f"0x{pid:04X}"] = val

                out.append({"folder": path, "properties": props})
                max_items -= 1

        # Rekursiv untergeordnete Ordner
        for sf in range(folder.number_of_sub_folders):
            walk(folder.get_sub_folder(sf), path)

    walk(pst.get_root_folder())
    pst.close()
    return {"items": out}


SUBJECT  = 0x0037
START_WHOLE = 0x8004
END_WHOLE   = 0x8005

def _get_str(msg, tag):
    raw = msg.get_property(tag)
    if raw is None:
        return None
    try:
        # UTF-16-LE ohne Low-Level-Reste wie \u0001\u0000\u0001\u0000
        txt = raw.decode("utf-16-le", errors="ignore").lstrip("\u0000\u0001")
        return txt.strip("\x00")
    except UnicodeDecodeError:
        return None

def _get_dt(msg, tag):
    raw = msg.get_property(tag)
    if raw and len(raw)==8:
        ticks, = struct.unpack("<Q", raw)
        dt = datetime.datetime(1601,1,1)+datetime.timedelta(microseconds=ticks/10)
        return dt.isoformat()
    return None

# MAPI–Tags, die wir schon gesehen haben
SUBJECT_TAG      = 0x0037
START_TAG        = 0x8004   # PR_START_DATE     (Appointments)
END_TAG          = 0x8005   # PR_END_DATE       (Appointments)

def _get_string(msg, tag):
    """
    Liefert einen String-Property-Wert oder None.
    """
    try:
        return msg.get_value_string(tag)          # ASCII
    except (AttributeError, IOError):
        pass
    try:
        return msg.get_value_string_wide(tag)     # Unicode
    except (AttributeError, IOError):
        pass

    # Fallbacks für sehr alte libpff-Versionen
    if tag == SUBJECT_TAG and hasattr(msg, "subject"):
        return msg.subject
    return None


def _get_datetime(msg, tag):
    """
    Liefert einen datetime-Property-Wert oder None.
    """
    try:
        return msg.get_value_datetime(tag)
    except (AttributeError, IOError):
        return None

def list_calendar_entries(pst_path: str):
    """
    Gibt alle Kalendereinträge mit Betreff, Start und Ende zurück.
    """
    import datetime
    import pypff

    pst = pypff.file()
    pst.open(pst_path)

    results = []

    def walk(folder, folder_name=""):
        folder_name = folder_name or (folder.name or "(kein Name)")

        # ---- Nachrichten dieses Ordners -----------------------------------
        for i in range(_folder_count_msgs(folder)):
            msg = _folder_get_message(folder, i)
            if msg is None:
                continue

            # MessageClass prüfen
            mc = (_get_string(msg, 0x001A) or "").upper()
            if not mc.startswith("IPM.APPOINTMENT"):
                continue

            subj  = _get_string(msg, SUBJECT_TAG)
            start = _get_datetime(msg, START_TAG)
            end   = _get_datetime(msg, END_TAG)

            results.append({
                "folder": folder_name,
                "subject": subj,
                "start":   start.isoformat() if isinstance(start, datetime.datetime) else None,
                "end":     end.isoformat()   if isinstance(end,   datetime.datetime) else None,
            })

        # ---- Unterordner rekursiv -----------------------------------------
        for j in range(_folder_count_subfolders(folder)):
            sub = _folder_get_subfolder(folder, j)
            if sub:
                walk(sub, f"{folder_name}/{sub.name or '(kein Name)'}")

    walk(pst.get_root_folder())
    pst.close()
    return results



