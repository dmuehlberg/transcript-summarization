#!/usr/bin/env python3
"""
Test für den neuen CSV-Import-Endpoint mit externen CSV-Dateien
"""

import requests
import tempfile
import os
import csv

def create_test_external_csv():
    """Erstellt eine Test-CSV-Datei im externen Format"""
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    
    # Testdaten im externen Format basierend auf Calendar_external_short.csv
    test_data = [
        {
            'Subject': 'Test External Meeting 1',
            'ClientSubmitTime': '2024-01-15 10:00:00',
            'SentRepresentingName': 'Test User',
            'StartDate': '2024-01-15 11:00:00',
            'EndDate': '2024-01-15 12:00:00',
            'ConversationTopic': 'Test conversation',
            'SenderName': 'Test Sender',
            'DisplayCc': 'cc@test.com',
            'DisplayTo': 'to@test.com',
            'undocumented 0x0e05': 'test_value_1',
            'MessageDeliveryTime': '2024-01-15 10:30:00',
            'undocumented 0x0f02': '2024-01-15 10:35:00',
            'undocumented 0x0f0a': '2024-01-15 10:40:00',
            'CreationTime': '2024-01-15 10:00:00',
            'LastModifierName': '2024-01-15 10:45:00',
            'CreatorSimpleDisplayName': 'Test Creator',
            'SenderSmtpAddress': 'sender@test.com',
            'SentRepresentingSmtpAddress': 'representing@test.com',
            'UserEntryId': 'test_entry_id',
            'PS_PUBLIC_STRINGS: SkypeTeamsMeetingUrl': 'https://teams.microsoft.com/test',
            'PSETID_Appointment: Location': 'Conference Room B'
        },
        {
            'Subject': 'Test External Meeting 2',
            'ClientSubmitTime': '2024-01-16 14:00:00',
            'SentRepresentingName': 'Another User',
            'StartDate': '2024-01-16 15:00:00',
            'EndDate': '2024-01-16 16:00:00',
            'ConversationTopic': 'Another conversation',
            'SenderName': 'Another Sender',
            'DisplayCc': 'cc2@test.com',
            'DisplayTo': 'to2@test.com',
            'undocumented 0x0e05': 'test_value_2',
            'MessageDeliveryTime': '2024-01-16 14:30:00',
            'undocumented 0x0f02': '2024-01-16 14:35:00',
            'undocumented 0x0f0a': '2024-01-16 14:40:00',
            'CreationTime': '2024-01-16 14:00:00',
            'LastModifierName': '2024-01-16 14:45:00',
            'CreatorSimpleDisplayName': 'Another Creator',
            'SenderSmtpAddress': 'sender2@test.com',
            'SentRepresentingSmtpAddress': 'representing2@test.com',
            'UserEntryId': 'test_entry_id_2',
            'PS_PUBLIC_STRINGS: SkypeTeamsMeetingUrl': 'https://teams.microsoft.com/test2',
            'PSETID_Appointment: Location': 'Virtual Meeting'
        }
    ]
    
    # Schreibe CSV-Datei
    if test_data:
        fieldnames = test_data[0].keys()
        writer = csv.DictWriter(temp_file, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(test_data)
    
    temp_file.close()
    return temp_file.name

def test_external_csv_import():
    """Testet den CSV-Import mit externer Quelle"""
    csv_file_path = create_test_external_csv()
    
    try:
        # Teste den Endpoint
        url = "http://localhost:8000/import-calendar-csv"
        
        with open(csv_file_path, 'rb') as f:
            files = {'file': ('test_external.csv', f, 'text/csv')}
            data = {
                'table_name': 'calendar_data',
                'source': 'external'
            }
            
            print("Sende externe CSV-Datei an den Endpoint...")
            response = requests.post(url, files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Erfolgreich!")
                print(f"Status: {result.get('status')}")
                print(f"Nachricht: {result.get('message')}")
                print(f"Tabelle: {result.get('table_name')}")
                print(f"Dateiname: {result.get('filename')}")
            else:
                print(f"❌ Fehler: {response.status_code}")
                print(f"Antwort: {response.text}")
                
    except Exception as e:
        print(f"❌ Fehler beim Testen: {str(e)}")
    finally:
        # Aufräumen
        if os.path.exists(csv_file_path):
            os.unlink(csv_file_path)
            print(f"Testdatei gelöscht: {csv_file_path}")

if __name__ == "__main__":
    print("Teste CSV-Import mit externer Quelle...")
    test_external_csv_import() 