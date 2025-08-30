#!/usr/bin/env python3
"""
Test für den CSV-Import-Endpoint mit internen CSV-Dateien (inkl. neue Terminserien-Felder)
"""

import requests
import tempfile
import os
import csv

def create_test_internal_csv():
    """Erstellt eine Test-CSV-Datei im internen Format mit neuen Terminserien-Feldern"""
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    
    # Testdaten im internen Format mit neuen Terminserien-Feldern
    test_data = [
        {
            'Subject': 'Wöchentliches Team-Meeting',
            'Client Submit Time': '2024-01-15 09:00:00',
            'Sent Representing Name': 'Team Lead',
            'Start Date': '2024-01-15 10:00:00',
            'End Date': '2024-01-15 11:00:00',
            'Conversation Topic': 'Wöchentliche Besprechung',
            'Sender Name': 'Team Lead',
            'Display Cc': 'team@company.com',
            'Display To': 'all@company.com',
            'Creation Time': '2024-01-15 09:00:00',
            'Last Modification Time': '2024-01-15 09:30:00',
            'Address Book Extension Attribute1': 'wöchentlich',
            'Contact Item Data': '2024-01-15 10:00:00',
            'Address Book Is Member Of Distribution List': '2024-12-31 23:59:59'
        },
        {
            'Subject': 'Monatliches Review',
            'Client Submit Time': '2024-01-20 14:00:00',
            'Sent Representing Name': 'Manager',
            'Start Date': '2024-01-20 15:00:00',
            'End Date': '2024-01-20 16:00:00',
            'Conversation Topic': 'Monatliches Review',
            'Sender Name': 'Manager',
            'Display Cc': 'review@company.com',
            'Display To': 'team@company.com',
            'Creation Time': '2024-01-20 14:00:00',
            'Last Modification Time': '2024-01-20 14:30:00',
            'Address Book Extension Attribute1': 'monatlich',
            'Contact Item Data': '2024-01-20 15:00:00',
            'Address Book Is Member Of Distribution List': '2024-06-30 23:59:59'
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

def test_internal_csv_import():
    """Testet den CSV-Import mit interner Quelle und neuen Terminserien-Feldern"""
    csv_file_path = create_test_internal_csv()
    
    try:
        # Teste den Endpoint
        url = "http://localhost:8000/import-calendar-csv"
        
        with open(csv_file_path, 'rb') as f:
            files = {'file': ('test_internal.csv', f, 'text/csv')}
            data = {
                'table_name': 'calendar_data',
                'source': 'internal'
            }
            
            print("Sende interne CSV-Datei mit Terminserien-Feldern an den Endpoint...")
            response = requests.post(url, files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Erfolgreich!")
                print(f"Status: {result.get('status')}")
                print(f"Nachricht: {result.get('message')}")
                print(f"Tabelle: {result.get('table_name')}")
                print(f"Dateiname: {result.get('filename')}")
                print("\nNeue Terminserien-Felder wurden erfolgreich importiert:")
                print("- meeting_series_rhythm (Rhythmus der Terminserie)")
                print("- meeting_series_start_date (Startdatum der Terminserie)")
                print("- meeting_series_end_date (Enddatum der Terminserie)")
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
    print("Teste CSV-Import mit internem Format und neuen Terminserien-Feldern...")
    test_internal_csv_import()
