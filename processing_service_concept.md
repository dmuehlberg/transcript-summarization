Implementation concept for a new macOS calendar endpoint

This plan serves as the implementation guide for Cursor. The goal is to add an endpoint in xstexport-service that executes export_calendar.scpt on a macOS host, parses the resulting XML file and optionally stores its contents in the existing Postgres table.

1. Calendar column
Extend app/config/calendar_mapping.json with an entry "Calendar".

"Calendar": {
  "pg_field": "calendar",
  "pg_type": "text"
}
Because the table is recreated each time the container starts, no ALTER TABLE logic is required. Creating the table using the mapping will automatically include this new column.

2. DatabaseService
Add a new method insert_calendar_events(self, events: List[Dict[str, Any]]) in app/services/db_service.py.

Convert the list of event dictionaries to a pandas DataFrame.

Use to_sql(..., if_exists='append') with the existing SQLAlchemy engine to insert into calendar_data.

Existing methods remain unchanged; they already handle table creation from the mapping.

3. mac_calendar_service
Create app/services/mac_calendar_service.py with two functions:

run_applescript() -> Path

Locate export_calendar.scpt in the project root.

Execute it via osascript, return the path to the resulting outlook_calendar_export_with_attendees.xml.

parse_calendar_xml(xml_path: Path) -> List[Dict[str, Any]]

Use xml.etree.ElementTree to read the XML.

Extract <calendar>, <subject>, <start>, <end>, <location>, <content>, <requiredAttendees>, <optionalAttendees>.

Convert start/end to datetimes via pandas.to_datetime.

Flatten attendee information into strings suitable for the columns display_to and display_cc.

Return a list of dictionaries with keys:
calendar, subject, start_date, end_date, has_picture, user_entry_id, display_to, display_cc.

4. New endpoint
In app/main.py define a POST endpoint /mac/export-calendar.

Flow:

Abort with HTTPException(400) if platform.system() is not "Darwin".

Call run_applescript() to create the XML file.

Parse the XML via parse_calendar_xml().

Optional form or query parameter import_to_db (default False): if True, insert events using db_service.insert_calendar_events.

Respond with JSON indicating success, number of events, and the XML path.

5. Documentation
Add a short section to the README (or a dedicated README for xstexport-service) describing the new endpoint, its macOS requirement and how to call it.