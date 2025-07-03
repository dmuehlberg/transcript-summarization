-- Verzeichnis des Skripts ermitteln
set scriptPath to (POSIX path of (path to me))
set scriptDir to do shell script "dirname " & quoted form of scriptPath

-- Zielpfad für die XML-Datei im gleichen Verzeichnis wie das Skript
set outputPath to (POSIX file (scriptDir & "/outlook_calendar_export_with_attendees.xml"))

-- XML-Dokument vorbereiten
set xmlContent to "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<calendarEvents>\n"

tell application "Microsoft Outlook"
	set theCalendars to calendars
	repeat with cal in theCalendars
		set calendarItems to calendar events of cal
		repeat with evt in calendarItems
			set evtSubject to subject of evt
			set evtStart to start time of evt
			set evtEnd to end time of evt
			set evtLocation to location of evt
			set evtContent to content of evt

			-- Teilnehmer extrahieren
			set requiredAttendees to required attendees of evt
			set optionalAttendees to optional attendees of evt

			-- Event-Start
			set xmlContent to xmlContent & "  <event>\n"
			set xmlContent to xmlContent & "    <calendar>" & my escapeXML(name of cal) & "</calendar>\n"
			set xmlContent to xmlContent & "    <subject>" & my escapeXML(evtSubject) & "</subject>\n"
			set xmlContent to xmlContent & "    <start>" & (evtStart as string) & "</start>\n"
			set xmlContent to xmlContent & "    <end>" & (evtEnd as string) & "</end>\n"
			set xmlContent to xmlContent & "    <location>" & my escapeXML(evtLocation) & "</location>\n"
			set xmlContent to xmlContent & "    <content>" & my escapeXML(evtContent) & "</content>\n"

			-- Pflichtteilnehmer
			set xmlContent to xmlContent & "    <requiredAttendees>\n"
			repeat with r in requiredAttendees
				set rName to ""
				try
					set rName to name of r
				end try
				set rEmail to ""
				try
					set rEmail to address of r
				end try
				set xmlContent to xmlContent & "      <attendee name=\"" & my escapeXML(rName) & "\" email=\"" & my escapeXML(rEmail) & "\" />\n"
			end repeat
			set xmlContent to xmlContent & "    </requiredAttendees>\n"

			-- Optionale Teilnehmer
			set xmlContent to xmlContent & "    <optionalAttendees>\n"
			repeat with o in optionalAttendees
				set oName to ""
				try
					set oName to name of o
				end try
				set oEmail to ""
				try
					set oEmail to address of o
				end try
				set xmlContent to xmlContent & "      <attendee name=\"" & my escapeXML(oName) & "\" email=\"" & my escapeXML(oEmail) & "\" />\n"
			end repeat
			set xmlContent to xmlContent & "    </optionalAttendees>\n"

			-- Event-Ende
			set xmlContent to xmlContent & "  </event>\n"
		end repeat
	end repeat
end tell

-- XML abschließen
set xmlContent to xmlContent & "</calendarEvents>\n"

-- Datei schreiben
do shell script "echo " & quoted form of xmlContent & " > " & quoted form of POSIX path of outputPath

-- XML-Escape-Funktion
on escapeXML(theText)
	if theText is missing value then set theText to ""
	set theText to my replaceText("&", "&amp;", theText)
	set theText to my replaceText("<", "&lt;", theText)
	set theText to my replaceText(">", "&gt;", theText)
	set theText to my replaceText("\"", "&quot;", theText)
	set theText to my replaceText("'", "&apos;", theText)
	return theText
end escapeXML

-- Hilfsfunktion: Text ersetzen
on replaceText(find, replace, textInput)
	set AppleScript's text item delimiters to find
	set textItems to every text item of textInput
	set AppleScript's text item delimiters to replace
	set newText to textItems as string
	set AppleScript's text item delimiters to ""
	return newText
end replaceText