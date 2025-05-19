# property_utils.py
from date_utils import convert_filetime_to_datetime

def extract_properties(msg, properties_to_check):
    """Extrahiert bestimmte Eigenschaften einer Nachricht."""
    # Diese Funktion extrahiert die Eigenschaften einer Nachricht mit Fokus auf Kalendereigenschaften
    
    props = {}
    
    # Nachrichtenklasse zuerst ermitteln
    msg_class = None
    try:
        if hasattr(msg, "get_message_class"):
            msg_class = msg.get_message_class()
        elif hasattr(msg, "property_values") and 0x001A in msg.property_values:
            msg_class = msg.property_values[0x001A]
        elif hasattr(msg, "get_property_data"):
            msg_class = msg.get_property_data(0x001A)
            
        # String-Konvertierung
        if isinstance(msg_class, bytes):
            msg_class = msg_class.decode('utf-8', errors='ignore')
        else:
            msg_class = str(msg_class or "Unknown")
    except Exception as e:
        msg_class = f"Error getting class: {str(e)}"
    
    props["Message Class"] = msg_class
    
    # Alle relevanten Eigenschaften durchgehen
    for prop_id, prop_name in properties_to_check.items():
        try:
            # Wert über verschiedene Methoden extrahieren
            value = None
            if hasattr(msg, "property_values") and prop_id in msg.property_values:
                value = msg.property_values[prop_id]
            elif hasattr(msg, "get_property_data"):
                try:
                    value = msg.get_property_data(prop_id)
                except:
                    pass
            
            # Bereinigen und konvertieren
            if value is not None:
                if isinstance(value, bytes):
                    try:
                        # Für Datum/Zeitwerte
                        if prop_id in [0x8004, 0x8005, 0x003D, 0x0023, 0x8502]:
                            # Versuchen, als Datumsstring zu interpretieren
                            if b":" in value and b"-" in value:  # Wahrscheinlich ein ISO-Datum
                                value = value.decode('utf-8', errors='ignore').strip('\x00')
                            else:
                                # Möglicherweise ein binäres Datum - als HEX ausgeben
                                value = value.hex()
                        else:
                            # Standardkonvertierung für Strings
                            value = value.decode('utf-8', errors='ignore').strip('\x00')
                    except Exception:
                        # Fallback auf Hex-Darstellung
                        value = value.hex()
                props[prop_name] = value
        except Exception as e:
            # Fehler protokollieren, aber fortfahren
            print(f"Fehler beim Extrahieren von {prop_name}: {str(e)}")
    
    return props, msg_class

def extract_all_properties(msg):
    """Extrahiert alle verfügbaren Eigenschaften einer Nachricht."""
    props = {}
    
    # Versuchen, property_values zu bekommen (moderne API)
    if hasattr(msg, "property_values"):
        # Alle Properties durchgehen
        for prop_id, value in msg.property_values.items():
            prop_name = f"0x{prop_id:04X}"  # Hex-Format für unbekannte IDs
            
            # Bereinigen und konvertieren
            if value is not None:
                if isinstance(value, bytes):
                    try:
                        # Für Datumswerte
                        if prop_id in [0x8004, 0x8005, 0x003D, 0x0023, 0x8502]:
                            if b":" in value and b"-" in value:  # ISO-Datum
                                value = value.decode('utf-8', errors='ignore').strip('\x00')
                            else:
                                value = value.hex()
                        else:
                            # Standardkonvertierung
                            value = value.decode('utf-8', errors='ignore').strip('\x00')
                    except Exception:
                        value = value.hex()
                props[prop_name] = value
    
    # Ältere API-Methode
    elif hasattr(msg, "get_number_of_properties"):
        try:
            for i in range(msg.get_number_of_properties()):
                try:
                    prop_id = msg.get_property_tag(i)
                    value = msg.get_property_data(prop_id)
                    
                    prop_name = f"0x{prop_id & 0xFFFF:04X}"  # Hex-Format
                    
                    # Bereinigen und konvertieren
                    if value is not None:
                        if isinstance(value, bytes):
                            try:
                                value = value.decode('utf-8', errors='ignore').strip('\x00')
                            except Exception:
                                value = value.hex()
                        props[prop_name] = value
                except Exception as e:
                    print(f"Fehler bei Property {i}: {str(e)}")
        except Exception as e:
            print(f"Fehler beim Zugriff auf Properties: {str(e)}")
    
    return props
    pass

def extract_all_properties_enhanced(msg):
    """
    Extrahiert ALLE verfügbaren Eigenschaften einer Nachricht mit erweiterter Erkennungslogik.
    
    Args:
        msg: Die Nachricht (pypff-Objekt)
        
    Returns:
        Ein Dictionary mit allen gefundenen Eigenschaften
    """
    all_props = {}
    debug_info = []
    
    # 1. Direkte Eigenschaftswerte über property_values (moderne API)
    if hasattr(msg, "property_values"):
        try:
            for prop_id, value in msg.property_values.items():
                prop_name = f"0x{prop_id:04X}"
                
                # Spezielle Behandlung für bestimmte Eigenschaftswerte
                if isinstance(value, bytes):
                    # Für Datumsfelder
                    if prop_id in [0x8004, 0x8005, 0x003D, 0x0023]:
                        if b":" in value and b"-" in value:
                            try:
                                text_value = value.decode('utf-8', errors='ignore').strip('\x00')
                                all_props[prop_name] = text_value
                            except:
                                all_props[prop_name] = f"Datum (binär): {value.hex()}"
                        else:
                            # Versuchen, als FILETIME zu interpretieren
                            try:
                                date_value = convert_filetime_to_datetime(value)
                                if date_value:
                                    all_props[prop_name] = date_value
                                else:
                                    all_props[prop_name] = f"Binär (wahrscheinlich Datum): {value.hex()}"
                            except:
                                all_props[prop_name] = f"Binär: {value.hex()}"
                    else:
                        # Allgemeine Textkonvertierung für andere Eigenschaften
                        try:
                            text_value = value.decode('utf-8', errors='ignore').strip('\x00')
                            # Prüfen, ob der String sinnvoll ist (mindestens ein alphanumerisches Zeichen)
                            if any(c.isalnum() for c in text_value):
                                all_props[prop_name] = text_value
                            else:
                                all_props[prop_name] = f"Binär: {value.hex()}"
                        except:
                            all_props[prop_name] = f"Binär: {value.hex()}"
                else:
                    all_props[prop_name] = value
                    
            debug_info.append(f"Über property_values: {len(all_props)} Eigenschaften gefunden")
        except Exception as e:
            debug_info.append(f"Fehler bei property_values: {str(e)}")
    
    # 2. Zugriff über get_number_of_properties und get_property_* (ältere API)
    # Dies könnte zusätzliche Eigenschaften offenbaren, die im property_values dict nicht enthalten sind
    if hasattr(msg, "get_number_of_properties"):
        try:
            num_props = msg.get_number_of_properties()
            debug_info.append(f"get_number_of_properties: {num_props} Eigenschaften gemeldet")
            
            # Alle verfügbaren Eigenschaften durchgehen
            for i in range(num_props):
                try:
                    prop_type = msg.get_property_type(i)
                    prop_tag = msg.get_property_tag(i)
                    prop_name = f"0x{prop_tag:04X}"
                    
                    # Wert abrufen, falls noch nicht vorhanden
                    if prop_name not in all_props:
                        try:
                            value = msg.get_property_data(prop_tag)
                            
                            # Wert konvertieren (ähnliche Logik wie oben)
                            if isinstance(value, bytes):
                                # Für Datumsfelder
                                if prop_tag in [0x8004, 0x8005, 0x003D, 0x0023]:
                                    if b":" in value and b"-" in value:
                                        text_value = value.decode('utf-8', errors='ignore').strip('\x00')
                                        all_props[prop_name] = text_value
                                    else:
                                        # Versuchen, als FILETIME zu interpretieren
                                        try:
                                            date_value = convert_filetime_to_datetime(value)
                                            if date_value:
                                                all_props[prop_name] = date_value
                                            else:
                                                all_props[prop_name] = f"Binär (Datum): {value.hex()}"
                                        except:
                                            all_props[prop_name] = f"Binär: {value.hex()}"
                                else:
                                    # Allgemeine Textkonvertierung
                                    try:
                                        text_value = value.decode('utf-8', errors='ignore').strip('\x00')
                                        if any(c.isalnum() for c in text_value):
                                            all_props[prop_name] = text_value
                                        else:
                                            all_props[prop_name] = f"Binär: {value.hex()}"
                                    except:
                                        all_props[prop_name] = f"Binär: {value.hex()}"
                            else:
                                all_props[prop_name] = value
                        except Exception as e:
                            all_props[f"{prop_name}_error"] = f"Fehler: {str(e)}"
                except Exception as e:
                    debug_info.append(f"Fehler bei Property {i}: {str(e)}")
                    
            debug_info.append(f"Nach get_property_*: Insgesamt {len(all_props)} Eigenschaften gefunden")
        except Exception as e:
            debug_info.append(f"Fehler bei get_number_of_properties: {str(e)}")
    
    # 3. Gezieltes Abtasten nach häufigen MAPI-Eigenschaften, die möglicherweise bisher verborgen sind
    common_props = [
        # Standardeigenschaften für Nachrichten
        0x001A, 0x0037, 0x003D, 0x1000, 0x0E1D, 0x0070, 0x0E04, 0x0E03, 0x0062, 0x0FFF,
        # Kalenderspezifische Eigenschaften 
        0x8004, 0x8005, 0x0024, 0x8201, 0x8216, 0x8580, 0x8582, 0x8501,
        # Verschiedene alternative Formate und Variationen
        0x001A001F, 0x0037001F, 0x1000001F, 0x0E04001F
    ]
    
    # Erweiterte Bereiche für bestimmte Eigenschaftstypen durchsuchen
    for base in [0x8000, 0x8100, 0x8200, 0x8300, 0x8400, 0x8500, 0x8600]:
        for offset in range(0, 0xFF, 10):  # In Schritten von 10, um Zeit zu sparen
            common_props.append(base + offset)
    
    for prop_id in common_props:
        prop_name = f"0x{prop_id:04X}"
        if prop_name not in all_props:
            try:
                value = None
                if hasattr(msg, "get_property_data"):
                    value = msg.get_property_data(prop_id)
                
                if value is not None:
                    # Wert konvertieren (ähnlich wie oben)
                    if isinstance(value, bytes):
                        try:
                            text_value = value.decode('utf-8', errors='ignore').strip('\x00')
                            if any(c.isalnum() for c in text_value):
                                all_props[prop_name] = text_value
                                debug_info.append(f"Zusätzliche Property {prop_name} gefunden")
                            else:
                                # Für nichtdruckbare Zeichen Binärformat verwenden
                                all_props[prop_name] = f"Binär: {value.hex()}"
                        except:
                            all_props[prop_name] = f"Binär: {value.hex()}"
                    else:
                        all_props[prop_name] = value
                        debug_info.append(f"Zusätzliche Property {prop_name} gefunden")
            except Exception:
                # Fehler ignorieren, da es normal ist, dass nicht alle Properties existieren
                pass
    
    # 4. Versuch, Named Properties zu extrahieren (falls verfügbar)
    # Dies ist ein experimenteller Ansatz, da pypff keine direkte API für Named Properties bietet
    if hasattr(msg, "get_named_properties"):
        try:
            named_props = msg.get_named_properties()
            for prop_name, prop_value in named_props.items():
                all_props[f"Named_{prop_name}"] = prop_value
                debug_info.append(f"Named Property {prop_name} gefunden")
        except Exception as e:
            debug_info.append(f"Fehler bei Named Properties: {str(e)}")
    
    # Debug-Info an alle_props anhängen (optional)
    all_props["_debug_info"] = debug_info
    
    return all_props
    pass

def get_property_value(msg, prop_id, property_name=None):
    """
    Versucht, den Wert einer Eigenschaft mit mehreren Methoden zu erhalten.
    
    Args:
        msg: Die Nachricht (pypff-Objekt)
        prop_id: Property-ID (int oder hex-string)
        property_name: Optionaler Name für Debug-Ausgaben
        
    Returns:
        Der Wert der Eigenschaft oder None, wenn nicht gefunden
    """
    value = None
    debug_info = []
    
    try:
        # Property-ID konvertieren, falls nötig
        if isinstance(prop_id, str):
            if prop_id.startswith("0x"):
                prop_id = int(prop_id, 16)
            else:
                prop_id = int(prop_id)
        
        # Methode 1: Über property_values dict (moderne API)
        if hasattr(msg, "property_values") and prop_id in msg.property_values:
            value = msg.property_values[prop_id]
            debug_info.append(f"Gefunden über property_values[{prop_id}]")
        
        # Methode 2: Über get_property_value (falls vorhanden)
        elif hasattr(msg, "get_property_value"):
            try:
                value = msg.get_property_value(prop_id)
                if value is not None:
                    debug_info.append(f"Gefunden über get_property_value({prop_id})")
            except Exception as e:
                debug_info.append(f"get_property_value Fehler: {str(e)}")
        
        # Methode 3: Über get_property_data (ältere API)
        elif hasattr(msg, "get_property_data"):
            try:
                value = msg.get_property_data(prop_id)
                if value is not None:
                    debug_info.append(f"Gefunden über get_property_data({prop_id})")
            except Exception as e:
                debug_info.append(f"get_property_data Fehler: {str(e)}")
        
        # Bereinigen und Konvertieren des Wertes
        if value is not None:
            if isinstance(value, bytes):
                # Verarbeitung für verschiedene Eigenschaftstypen
                try:
                    # Für Datums-/Zeitwerte
                    if prop_id in [0x8004, 0x8005, 0x003D, 0x0023, 0x8502, 
                                0x00430102, 0x00440102, 0x0002, 0x0003, 
                                0x0060, 0x0061, 0x82000102, 0x82010102]:
                        # Versuchen als ISO-Datum zu dekodieren
                        if b":" in value and b"-" in value:
                            value = value.decode('utf-8', errors='ignore').strip('\x00')
                            debug_info.append("Als ISO-Datum dekodiert")
                        else:
                            # Falls binäres Format, umwandeln
                            # TODO: Korrekte Datumskonvertierung 
                            # von binärem FILETIME Format hinzufügen
                            value = f"Binäres Datum: {value.hex()}"
                            debug_info.append("Binäres Datum als Hex")
                    else:
                        # Standard-Stringkonvertierung für Text
                        value = value.decode('utf-8', errors='ignore').strip('\x00')
                        debug_info.append("Als UTF-8 String dekodiert")
                except Exception as e:
                    value = f"Binäre Daten: {value.hex()}"
                    debug_info.append(f"Konvertierungsfehler: {str(e)}")
        
        # Debug-Informationen
        if property_name and debug_info:
            print(f"Property {property_name} (ID 0x{prop_id:X}): {', '.join(debug_info)}")
            
        return value
        
    except Exception as e:
        print(f"Fehler beim Zugriff auf Property 0x{prop_id:X}: {str(e)}")
        return None
    pass

def get_calendar_properties(msg):
    """
    Extrahiert alle für Kalendereinträge relevanten Eigenschaften mit erweiterten Methoden.
    
    Args:
        msg: Die Nachricht (pypff-Objekt)
        
    Returns:
        Ein Dictionary mit den Eigenschaften des Kalendereintrags
    """
    calendar_data = {
        "raw_props": {},  # Alle rohen Eigenschaften
        "properties": {}  # Geordnete und bereinigte Eigenschaften
    }
    
    # Zuerst alle Eigenschaften extrahieren - für Debugging und Redundanz
    raw_props = extract_all_properties(msg)
    calendar_data["raw_props"] = raw_props
    
    # Nachrichtenklasse bestimmen
    msg_class = None
    for prop_id in [0x001A, 0x001A001F]:
        value = get_property_value(msg, prop_id)
        if value:
            msg_class = value
            break
    
    if not msg_class:
        msg_class = "Unknown"
    
    calendar_data["properties"]["MessageClass"] = msg_class
    
    # Kernfelder mit Fallback-Optionen extrahieren
    # 1. Betreff
    subject = None
    for prop_id in [0x0037, 0x0037001F, 0x0E1D, 0x0070]:
        value = get_property_value(msg, prop_id)
        if value:
            subject = value
            calendar_data["properties"]["Subject"] = value
            break
    
    # 2. Startzeit - mehrere mögliche Property-IDs probieren
    for prop_id in [0x8004, 0x00430102, 0x0002, 0x0060, 0x82000102, 0x82050102]:
        value = get_property_value(msg, prop_id)
        if value:
            calendar_data["properties"]["StartTime"] = value
            break
    
    # 3. Endzeit - mehrere mögliche Property-IDs probieren
    for prop_id in [0x8005, 0x00440102, 0x0003, 0x0061, 0x82010102, 0x82060102]:
        value = get_property_value(msg, prop_id)
        if value:
            calendar_data["properties"]["EndTime"] = value
            break
    
    # 4. Ort - mehrere mögliche Property-IDs probieren
    for prop_id in [0x0024, 0x0094, 0x8208]:
        value = get_property_value(msg, prop_id)
        if value:
            calendar_data["properties"]["Location"] = value
            break
    
    # 5. Textkörper - versuche mehrere Formate
    body = None
    
    # Plain Text
    for prop_id in [0x1000, 0x1000001F]:
        value = get_property_value(msg, prop_id)
        if value:
            body = value
            calendar_data["properties"]["Body"] = value
            break
    
    # HTML (falls kein Plain Text gefunden wurde oder zusätzlich)
    for prop_id in [0x0FFF, 0x1013, 0x1014]:
        value = get_property_value(msg, prop_id)
        if value:
            calendar_data["properties"]["HtmlBody"] = value
            # Falls noch kein Body gefunden wurde, HTML als Fallback verwenden
            if "Body" not in calendar_data["properties"]:
                # HTML-Tags entfernen für eine einfache Textdarstellung
                text_body = re.sub(r'<[^>]+>', ' ', value)
                text_body = re.sub(r'\s+', ' ', text_body).strip()
                calendar_data["properties"]["Body"] = text_body
            break
    
    # RTF Compressed (als letzter Versuch)
    rtf_value = get_property_value(msg, 0x1009)
    if rtf_value and "Body" not in calendar_data["properties"]:
        calendar_data["properties"]["RtfCompressed"] = "RTF data available (binary)"
    
    # 6. Teilnehmer 
    for prop_id in [0x0E04, 0x0E04001F]:
        value = get_property_value(msg, prop_id)
        if value:
            calendar_data["properties"]["DisplayTo"] = value
            break
    
    # 7. Organisator-Informationen
    for prop_id in [0x0042, 0x0081, 0x001F]:
        value = get_property_value(msg, prop_id)
        if value:
            calendar_data["properties"]["Organizer"] = value
            break
    
    # 8. Wichtige Flags
    # Ganztägiges Ereignis
    all_day = get_property_value(msg, 0x8216)
    if all_day is not None:
        calendar_data["properties"]["AllDayEvent"] = all_day
    
    # Erinnerung gesetzt
    reminder_set = get_property_value(msg, 0x8501)
    if reminder_set is not None:
        calendar_data["properties"]["ReminderSet"] = reminder_set
    
    # Erinnerungszeit
    reminder_minutes = get_property_value(msg, 0x0065)
    if reminder_minutes is not None:
        calendar_data["properties"]["ReminderMinutesBeforeStart"] = reminder_minutes
    
    # Wiederholung
    is_recurring = get_property_value(msg, 0x8201)
    if is_recurring is not None:
        calendar_data["properties"]["IsRecurring"] = is_recurring
    
    # Wiederholungsmuster
    recurrence_pattern = get_property_value(msg, 0x8582)
    if recurrence_pattern:
        calendar_data["properties"]["RecurrencePattern"] = recurrence_pattern
    
    # 9. Weitere wichtige Eigenschaften hinzufügen, wenn vorhanden
    for prop_name, prop_id in property_map.items():
        # Überspringen von bereits verarbeiteten Kernfeldern
        if (prop_name in calendar_data["properties"] or 
            prop_name.endswith("_Alt") or 
            prop_name.endswith("_Alt1") or 
            prop_name.endswith("_Alt2") or
            prop_name.endswith("_Alt3") or
            prop_name.endswith("_Named") or
            prop_name.endswith("Unicode")):
            continue
            
        value = get_property_value(msg, prop_id)
        if value is not None:
            calendar_data["properties"][prop_name] = value
    
    # Ist dies wirklich ein Kalendereintrag?
    is_calendar = (
        "IPM.Appointment" in msg_class or
        "IPM.Schedule.Meeting" in msg_class or
        "calendar" in msg_class.lower() or
        "appointment" in msg_class.lower() or
        "meeting" in msg_class.lower() or
        "{00061055-0000-0000-C000-000000000046}" in msg_class
    )
    
    # Alternative Erkennung über vorhandene Kalendereigenschaften
    if not is_calendar:
        calendar_indicators = [
            "StartTime" in calendar_data["properties"],
            "EndTime" in calendar_data["properties"],
            "AllDayEvent" in calendar_data["properties"],
            "Location" in calendar_data["properties"] and "Body" in calendar_data["properties"],
            "ReminderSet" in calendar_data["properties"],
            # Weitere spezifische Indikatoren können hier hinzugefügt werden
        ]
        
        is_calendar = any(calendar_indicators)
    
    calendar_data["is_calendar_item"] = is_calendar
    
    return calendar_data
    pass