"""Light‑weight helper for pulling calendar information out of a PST/OST file
using **libpff / pypff**.  
The module tries very hard to cope with the slightly different property APIs
that various pypff builds expose.  **No external dependencies** other than
`pypff` and the Python std‑lib are required.

The public helpers that are intended to be imported from *main.py* are:

* ``list_folders(path)``                     – return folder tree
* ``dump_calendar_properties(path, max_items)`` – raw property dump for debugging
* ``list_calendar_entries(path, limit=None)``    – *clean* calendar list
* ``extract_calendar_entries(path)``            – same as above but only from
                                                  the first calendar folder
* ``extract_all_calendar_entries(path)``        – walk entire store and pull
                                                  every appointment like
                                                  message
* ``extract_attendees(path)``                    – demo that extracts the
                                                  PR_DISPLAY_TO style attendee
                                                  list from an appointment

The code does **no** type‑checking / data‑clean‑up – that should be done in
FastAPI models.  Everything returned from here is plain JSON‑serialisable.
"""
from __future__ import annotations

import datetime as _dt
import os
from typing import Any, Dict, List

import pypff  # type: ignore – compiled C extension

# ---------------------------------------------------------------------------
#  MAPI property tag helpers
# ---------------------------------------------------------------------------
# We only need a handful of well‑known IDs.  Keep them short & sweet.
PR_MESSAGE_CLASS = 0x001A  # W   – "IPM.Appointment" …
PR_SUBJECT_W      = 0x0037  # W   – Unicode subject line
PR_BODY_W         = 0x1000  # W
PR_DISPLAY_TO_W   = 0x0E04  # W   – comma separated attendee list

PSETID_APPT_START = 0x8004  # Systime – appointment start
PSETID_APPT_END   = 0x8005  # Systime – appointment end

# ---------------------------------------------------------------------------
#  Small util helpers
# ---------------------------------------------------------------------------

def _clean_str(raw: bytes | str | None) -> str | None:
    """Convert raw MAPI string (may be bytes with UTF‑16LE & NUL padding)"""
    if raw is None:
        return None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf‑16le", errors="ignore")
        except UnicodeDecodeError:
            raw = raw.decode(errors="ignore")
    # strip trailing NULs & odd prefix characters that some subjects contain
    return raw.replace("\x00", "").strip().strip("\u0001").strip()


def _clean_dt(raw: str | bytes | None) -> str | None:
    """Ensure we have an ISO‑8601 time string (pypff already returns one for
    systime properties)."""
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode(errors="ignore")
    raw = raw.strip("\x00")
    # Very small sanity check – if it contains a T we assume it is fine
    if "T" in raw:
        return raw
    # otherwise try to parse as YYYY‑MM‑DD HH:MM:SS
    try:
        return _dt.datetime.fromisoformat(raw.replace(" ", "T")).isoformat()
    except Exception:
        return None


# ---------------------------------------------------------------------------
#  Generic property access – cope with the various pypff versions
# ---------------------------------------------------------------------------

def _iter_properties(msg) -> Dict[int, Any]:
    """Return *all* properties as *{ proptag_without_type : data }*.

    Older pypff builds expose an iterator‑style API, newer ones a list of
    ``property_values``.  We try both and fall back to whatever is available.
    """
    props: dict[int, Any] = {}

    # 1) Easiest – the modern attribute exposed by Joachim Metz' fork
    pv = getattr(msg, "property_values", None)
    if pv:
        for tag, data in pv.items():
            # strip the lower 16‑bit type information so we can compare with
            # our short constants defined above (makes the code a lot nicer)
            props[tag & 0xFFFF] = data
        return props

    # 2) Classic getter style (get_number_of_properties / get_property_tag …)
    try:
        num = msg.get_number_of_properties()
        for idx in range(num):
            tag = msg.get_property_tag(idx)
            data = msg.get_property_data(tag)
            props[tag & 0xFFFF] = data
        return props
    except AttributeError:
        pass  # fall through – see 3)

    # 3) Very old builds expose ``_properties`` list of (tag, data)
    raw = getattr(msg, "_properties", None)
    if raw:
        for tag, data in raw:
            props[tag & 0xFFFF] = data
    return props


# ---------------------------------------------------------------------------
#  Core helpers that recognise a calendar item and extract interesting bits
# ---------------------------------------------------------------------------

def _is_appointment(props: Dict[int, Any]) -> bool:
    """Very naïve – if it *has* PSETID_APPT_START we assume it is an appointment."""
    return PSETID_APPT_START in props


def _mk_folder_path(folder) -> str:
    bits = []
    while folder is not None:
        nm = folder.name or "(kein Name)"
        bits.append(nm)
        folder = folder.parent
    return "/".join(reversed(bits))


def _mk_entry(folder, props):
    return {
        "folder": _mk_folder_path(folder),
        "subject": _clean_str(props.get(PR_SUBJECT_W)) or "(ohne Betreff)",
        "start": _clean_dt(props.get(PSETID_APPT_START)),
        "end": _clean_dt(props.get(PSETID_APPT_END)),
    }

# ---------------------------------------------------------------------------
#  Public functions
# ---------------------------------------------------------------------------

def list_folders(pst_path: str) -> List[dict]:
    """Return a *very* lightweight folder tree (for debugging)"""
    pst = pypff.file()
    pst.open(pst_path)

    tree = []

    def _walk(folder):
        tree.append({
            "path": _mk_folder_path(folder),
            "sub_folders": folder.number_of_sub_folders,
            "messages": folder.number_of_sub_messages,
        })
        for i in range(folder.number_of_sub_folders):
            _walk(folder.get_sub_folder(i))

    _walk(pst.get_root_folder())
    pst.close()
    return tree


# ---------------------------------------------------------------------------
#  Property dump (debug helper)
# ---------------------------------------------------------------------------

def dump_calendar_properties(pst_path: str, *, max_items: int = 5):
    """Dump *all* properties of the first *max_items* appointment messages.
    The function is incredibly useful during reverse‑engineering sessions.
    """
    pst = pypff.file()
    pst.open(pst_path)

    items: list[dict] = []

    def _walk(folder):
        nonlocal items
        for i in range(folder.number_of_sub_messages):
            if len(items) >= max_items:
                return
            msg = folder.get_sub_message(i)
            props = _iter_properties(msg)
            if _is_appointment(props):
                # stringify & clean for JSON output
                nice = {f"0x{tag:04X}": _clean_str(val) or _clean_dt(val) or repr(val) for tag, val in props.items()}
                items.append({"folder": _mk_folder_path(folder), "properties": nice})
        for j in range(folder.number_of_sub_folders):
            _walk(folder.get_sub_folder(j))

    _walk(pst.get_root_folder())
    pst.close()
    return {"items": items}

# ---------------------------------------------------------------------------
#  High‑level extraction helpers used by the FastAPI layer
# ---------------------------------------------------------------------------

def list_calendar_entries(pst_path: str, limit: int | None = None):
    """Return a *flat* list of appointments (folder, subject, start, end)."""
    pst = pypff.file()
    pst.open(pst_path)

    entries: list[dict] = []

    def _walk(folder):
        nonlocal entries
        for i in range(folder.number_of_sub_messages):
            msg = folder.get_sub_message(i)
            props = _iter_properties(msg)
            if not _is_appointment(props):
                continue
            entries.append(_mk_entry(folder, props))
            if limit and len(entries) >= limit:
                return
        for j in range(folder.number_of_sub_folders):
            if limit and len(entries) >= (limit or 0):
                return
            _walk(folder.get_sub_folder(j))

    _walk(pst.get_root_folder())
    pst.close()
    return entries


# The following helpers just call *list_calendar_entries* with different scopes
# ---------------------------------------------------------------------------

def extract_calendar_entries(pst_path: str):
    """Alias kept for backward compatibility – pulls *all* appointments."""
    return list_calendar_entries(pst_path)


def extract_all_calendar_entries(pst_path: str):
    return list_calendar_entries(pst_path)


# ---------------------------------------------------------------------------
#  Simple attendee list demo (very naïve!)
# ---------------------------------------------------------------------------

def extract_attendees(pst_path: str):
    pst = pypff.file()
    pst.open(pst_path)

    attendees: list[str] = []

    def _walk(folder):
        nonlocal attendees
        for i in range(folder.number_of_sub_messages):
            msg = folder.get_sub_message(i)
            props = _iter_properties(msg)
            if _is_appointment(props):
                to = _clean_str(props.get(PR_DISPLAY_TO_W))
                if to:
                    attendees.extend([a.strip() for a in to.split(";") if a.strip()])
        for j in range(folder.number_of_sub_folders):
            _walk(folder.get_sub_folder(j))

    _walk(pst.get_root_folder())
    pst.close()
    return attendees
