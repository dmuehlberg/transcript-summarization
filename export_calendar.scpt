-- Speicherort der XML-Datei
set outputPath to (POSIX file (POSIX path of (path to desktop folder) & "outlook_calendar_export_with_attendees.xml"))

-- XML-Dokument vorbereiten
set xmlContent to "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<calendarEvents>\n"

tell application "Microsoft Outlook"
	set calendarItems to calendar events of calendar of default account
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
		set xmlContent to xmlContent & "    <subject>" & escapeXML(evtSubject) & "</subject>\n"
		set xmlContent to xmlContent & "    <start>" & (evtStart as string) & "</start>\n"
		set xmlContent to xmlContent & "    <end>" & (evtEnd as string) & "</end>\n"
		set xmlContent to xmlContent & "    <location>" & escapeXML(evtLocation) & "</location>\n"
		set xmlContent to xmlContent & "    <content>" & escapeXML(evtContent) & "</content>\n"

		-- Pflichtteilnehmer
		set xmlContent to xmlContent & "    <requiredAttendees>\n"
		repeat with r in requiredAttendees
			set rName to name of r
			set rEmail to address of r
			set xmlContent to xmlContent & "      <attendee name=\"" & escapeXML(rName) & "\" email=\"" & escapeXML(rEmail) & "\" />\n"
		end repeat
		set xmlContent to xmlContent & "    </requiredAttendees>\n"

		-- Optionale Teilnehmer
		set xmlContent to xmlContent & "    <optionalAttendees>\n"
		repeat with o in optionalAttendees
			set oName to name of o
			set oEmail to address of o
			set xmlContent to xmlContent & "      <attendee name=\"" & escapeXML(oName) & "\" email=\"" & escapeXML(oEmail) & "\" />\n"
		end repeat
		set xmlContent to xmlContent & "    </optionalAttendees>\n"

		-- Event-Ende
		set xmlContent to xmlContent & "  </event>\n"
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