# constants.py
# MAPI-Eigenschaften für Kalendereinträge

CALENDAR_PROPS = {
        0x001A: "Message Class",               # PR_MESSAGE_CLASS
        0x0037: "Subject",                     # PR_SUBJECT
        0x003D: "Creation Time",               # PR_CREATION_TIME (nur Info)
        0x1000: "Body",                        # PR_BODY
        0x0C1A: "Sender Name",                 # PR_SENDER_NAME
        0x8004: "Start Time",                  # PidLidAppointmentStartWhole
        0x8005: "End Time",                    # PidLidAppointmentEndWhole
        0x0063: "Response Status",             # PidLidResponseStatus
        0x0024: "Location",                    # PidLidLocation
        0x0065: "Reminder Minutes",            # PidLidReminderMinutesBeforeStart
        0x0E1D: "Normalized Subject",          # PR_NORMALIZED_SUBJECT
        0x0070: "Topic",                       # PR_CONVERSATION_TOPIC
        0x0023: "Creation Time",               # PR_LAST_MODIFICATION_TIME
        0x0E04: "Display To",                  # PR_DISPLAY_TO (Liste der Teilnehmer)
        0x0E03: "Display CC",                  # PR_DISPLAY_CC
        0x0062: "Importance",                  # PR_IMPORTANCE
        0x0017: "Importance",                  # PR_IMPORTANCE (zweite Methode)
        0x0036: "Sensitivity",                 # PR_SENSITIVITY
        0x000F: "Reply To",                    # PR_REPLY_RECIPIENT_NAMES
        0x0FFF: "Body HTML",                   # PR_HTML
        0x0C1F: "Sender Address Type",         # PR_SENDER_ADDRTYPE
        0x0075: "Received By Name",            # PR_RECEIVED_BY_NAME
        0x0E1F: "Message Status",              # PR_MSG_STATUS
        0x8201: "Is Recurring",                # Wiederholung - PidLidAppointmentRecur
        0x8216: "All Day Event",               # PidLidAppointmentAllDayEvent
        0x0E2D: "Has Attachment",              # PR_HASATTACH (Anhänge)
        0x8580: "Recurrence Type",             # PidLidRecurrenceType
        0x8582: "Recurrence Pattern",          # PidLidRecurrencePattern
        0x8501: "Reminder Set",                # PidLidReminderSet
        0x001F: "Organizer",                   # PidTagSenderName
}
    
# Zusätzliche erweiterte Eigenschaften
EXTENDED_PROPS = {
        0x8530: "Appointment Color",           # PidLidAppointmentColor
        0x8502: "Reminder Time",               # PidLidReminderTime
        0x8560: "Attendee Type",               # Teilnehmertyp
        0x8518: "Appointment Type",            # PidLidAppointmentType
        0x8208: "Is Online Meeting",           # PidLidConferenceServer
        0x0029: "Description",                 # PidLidAutoStartCheck
        0x0020: "Attachment Files",            # PR_ATTACH_DATA_BIN
}

 # Standard MAPI-Properties, die für Kalendereinträge relevant sind
STANDARD_CAL_PROPS = {
    0x001A: "MessageClass",               # PR_MESSAGE_CLASS
    0x0037: "Subject",                     # PR_SUBJECT
    0x003D: "CreationTime",                # PR_CREATION_TIME
    0x1000: "Body",                        # PR_BODY
    0x0C1A: "SenderName",                  # PR_SENDER_NAME
    0x8004: "StartTime",                   # PidLidAppointmentStartWhole
    0x8005: "EndTime",                     # PidLidAppointmentEndWhole
    0x0063: "ResponseStatus",              # PidLidResponseStatus
    0x0024: "Location",                    # PidLidLocation
    0x0065: "ReminderMinutesBeforeStart",  # PidLidReminderMinutesBeforeStart
    0x0E1D: "NormalizedSubject",           # PR_NORMALIZED_SUBJECT
    0x0070: "ConversationTopic",           # PR_CONVERSATION_TOPIC
    0x0E04: "DisplayTo",                   # PR_DISPLAY_TO (Teilnehmerliste)
    0x0E03: "DisplayCC",                   # PR_DISPLAY_CC
    0x0062: "Importance",                  # PR_IMPORTANCE
    0x0FFF: "HtmlBody",                    # PR_HTML
    0x8201: "IsRecurring",                 # PidLidAppointmentRecur
    0x8216: "AllDayEvent",                 # PidLidAppointmentAllDayEvent
    0x0E2D: "HasAttachment",               # PR_HASATTACH
    0x8501: "ReminderSet",                 # PidLidReminderSet
    0x001F: "OrganizerName",               # PidTagSenderName
}

# Erweiterte Property-Set - alternative IDs und zusätzliche Eigenschaften
EXTENDED_CAL_PROPS = {
    # Alternative IDs für Standardeigenschaften
    0x00430102: "StartTime_Alt1",          # Alternative für Startzeit
    0x00440102: "EndTime_Alt1",            # Alternative für Endzeit
    0x0002: "StartTime_Alt2",              # Weitere Alternative für Startzeit
    0x0003: "EndTime_Alt2",                # Weitere Alternative für Endzeit
    0x0060: "StartTime_Alt3",              # Weitere Alternative für Startzeit
    0x0061: "EndTime_Alt3",                # Weitere Alternative für Endzeit
    0x82000102: "StartTime_Named",         # Named Property für Startzeit
    0x82010102: "EndTime_Named",           # Named Property für Endzeit
    0x82050102: "StartDate",               # Startdatum (Named Property)
    0x82060102: "EndDate",                 # Enddatum (Named Property)
    0x0094: "Location_Alt",                # Alternative für Ort
    0x8208: "Location_Named",              # Named Property für Ort
    
    # Zusätzliche Kalendereigenschaften
    0x8530: "AppointmentColor",            # PidLidAppointmentColor
    0x8502: "ReminderTime",                # PidLidReminderTime
    0x8560: "AttendeeType",                # Teilnehmertyp
    0x8518: "AppointmentType",             # PidLidAppointmentType
    0x8208: "IsOnlineMeeting",             # PidLidConferenceServer
    0x8582: "RecurrencePattern",           # PidLidRecurrencePattern
    0x8580: "RecurrenceType",              # PidLidRecurrenceType
    
    # Spezielle für RTF und HTML Inhalte
    0x1009: "RtfCompressed",               # PR_RTF_COMPRESSED
    0x1013: "HtmlContent",                 # Alternative HTML
    0x1014: "BodyContentId",               # Content-ID für HTML
    
    # Erweiterte Teilnehmer- und Organisator-Informationen
    0x0042: "OrganizerEmail",              # Organisator-E-Mail 
    0x0044: "ReceivedRepresentingName",    # Repräsentierende Person
    0x004D: "OrganizerAddressType",        # Organisator-Adresstyp
    0x0081: "OrganizerEmailAddress",       # E-Mail-Adresse des Organisators
    0x8084: "OrganizerPhoneNumber",        # Telefonnummer des Organisators
    
    # Anlagenspezifische Properties
    0x0E13: "AttachmentCount",             # Anzahl der Anlagen
    0x0E21: "AttachmentFiles",             # Anlagendateien
    
    # Für Unicode-Textfelder
    0x001F001F: "SubjectUnicode",          # Betreff (Unicode)
    0x0037001F: "SubjectAlt",              # Alternativer Betreff
    0x0070001F: "TopicUnicode",            # Thema (Unicode)
    0x1000001F: "BodyUnicode",             # Text (Unicode)
    0x0E04001F: "DisplayToUnicode",        # Empfänger (Unicode)
}