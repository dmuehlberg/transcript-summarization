Key files for context

processing_service/app/main.py

processing_service/README.md

The get_meeting_info endpoint reads meeting data from the table calendar_data within a configurable time window. Currently, both the single-recording and batch code paths query for a single (LIMIT 1) meeting; if no row is found a 404/error is returned. When multiple meetings exist for the specified recording date, the service simply returns the closest one.

Potential Issue / Enhancement
The user wants a different behavior: if more than one calendar entry falls into the time window for a given recording_date, the endpoint should not pick the closest meeting. Instead, the response should contain "meeting_title": "Multiple Meetings found" while the remaining meeting info fields stay empty. The database record for the affected transcription should be updated accordingly.