import pypff

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