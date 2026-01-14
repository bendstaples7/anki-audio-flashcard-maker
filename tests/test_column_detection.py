#!/usr/bin/env python3
"""
Test column detection with real data.
"""

from cantonese_anki_generator.processors import GoogleSheetsParser

def test_detection():
    parser = GoogleSheetsParser()
    
    # Get Google Sheets URL from user
    sheets_url = input("Enter your Google Sheets URL: ").strip()
    
    print("Getting sheet data...")
    sheet_data = parser.get_sheet_data(sheets_url)
    
    print("Raw data preview:")
    for i, row in enumerate(sheet_data[:5], 1):
        print(f"Row {i}: {row}")
    
    print("\nColumn detection:")
    eng_col, cant_col = parser.identify_vocabulary_columns(sheet_data)
    print(f"English column: {eng_col} ('{sheet_data[0][eng_col] if sheet_data else 'N/A'}')")
    print(f"Cantonese column: {cant_col} ('{sheet_data[0][cant_col] if sheet_data else 'N/A'}')")
    
    print("\nExtracting vocabulary:")
    entries = parser.extract_vocabulary_pairs(sheet_data)
    
    print(f"\nExtracted {len(entries)} entries:")
    for i, entry in enumerate(entries[:8], 1):
        print(f"{i}. English: \"{entry.english}\" → Cantonese: \"{entry.cantonese}\" (confidence: {entry.confidence:.2f})")

if __name__ == "__main__":
    test_detection()