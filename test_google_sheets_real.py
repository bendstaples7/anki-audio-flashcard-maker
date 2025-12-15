#!/usr/bin/env python3
"""
Real-world test script for Google Sheets processor.
"""

import sys
from cantonese_anki_generator.processors import GoogleSheetsParser, GoogleDocsAuthenticator


def test_google_sheets_processor():
    """Test the Google Sheets processor with a real spreadsheet."""
    
    print("📊 Testing Google Sheets Processor")
    print("=" * 50)
    
    # Get spreadsheet URL from user
    sheets_url = input("Enter Google Sheets URL: ").strip()
    
    if not sheets_url:
        print("❌ No URL provided")
        return False
    
    try:
        print("\n📋 Step 1: Initializing authenticator...")
        authenticator = GoogleDocsAuthenticator()
        
        print("📋 Step 2: Initializing sheets parser...")
        parser = GoogleSheetsParser(authenticator)
        
        print("📋 Step 3: Extracting spreadsheet ID...")
        spreadsheet_id = parser.extract_spreadsheet_id(sheets_url)
        print(f"   Spreadsheet ID: {spreadsheet_id}")
        
        print("📋 Step 4: Authenticating with Google...")
        if not authenticator.authenticate():
            print("❌ Authentication failed")
            return False
        print("   ✅ Authentication successful")
        
        print("📋 Step 5: Getting sheet names...")
        sheet_names = parser.get_sheet_names(sheets_url)
        print(f"   Found sheets: {', '.join(sheet_names)}")
        
        # Let user choose sheet if multiple
        sheet_name = None
        if len(sheet_names) > 1:
            print("\n📋 Multiple sheets found:")
            for i, name in enumerate(sheet_names, 1):
                print(f"   {i}. {name}")
            
            choice = input("Enter sheet number (or press Enter for first sheet): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(sheet_names):
                sheet_name = sheet_names[int(choice) - 1]
            else:
                sheet_name = sheet_names[0]
            
            print(f"   Using sheet: {sheet_name}")
        else:
            sheet_name = sheet_names[0] if sheet_names else None
        
        print("📋 Step 6: Getting sheet data...")
        sheet_data = parser.get_sheet_data(sheets_url, sheet_name)
        print(f"   ✅ Retrieved {len(sheet_data)} rows")
        
        if not sheet_data:
            print("❌ No data found in sheet")
            return False
        
        # Show preview of data
        print("\n📋 Step 7: Data preview:")
        for i, row in enumerate(sheet_data[:5]):  # Show first 5 rows
            print(f"   Row {i+1}: {row[:4]}")  # Show first 4 columns
        
        print("📋 Step 8: Identifying vocabulary columns...")
        english_col, cantonese_col = parser.identify_vocabulary_columns(sheet_data)
        print(f"   English column: {english_col + 1} ('{sheet_data[0][english_col] if sheet_data else 'N/A'}')")
        print(f"   Cantonese column: {cantonese_col + 1} ('{sheet_data[0][cantonese_col] if sheet_data else 'N/A'}')")
        
        print("📋 Step 9: Extracting vocabulary pairs...")
        vocabulary_entries = parser.extract_vocabulary_pairs(sheet_data)
        print(f"   ✅ Extracted {len(vocabulary_entries)} vocabulary entries")
        
        print("\n📊 Results:")
        print("=" * 30)
        for i, entry in enumerate(vocabulary_entries[:10], 1):  # Show first 10 entries
            print(f"{i:2d}. {entry.english:15} → {entry.cantonese:10} (confidence: {entry.confidence:.2f})")
        
        if len(vocabulary_entries) > 10:
            print(f"... and {len(vocabulary_entries) - 10} more entries")
        
        print(f"\n🎉 Success! Extracted {len(vocabulary_entries)} vocabulary pairs")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sheets_with_range():
    """Test Google Sheets with a specific range."""
    print("📊 Testing Google Sheets with Range")
    print("=" * 40)
    
    sheets_url = input("Enter Google Sheets URL: ").strip()
    if not sheets_url:
        print("❌ No URL provided")
        return False
    
    range_name = input("Enter range (e.g., A1:B10) or press Enter for all data: ").strip()
    if not range_name:
        range_name = None
    
    try:
        authenticator = GoogleDocsAuthenticator()
        parser = GoogleSheetsParser(authenticator)
        
        print("📋 Authenticating...")
        if not authenticator.authenticate():
            print("❌ Authentication failed")
            return False
        
        print("📋 Getting data...")
        sheet_data = parser.get_sheet_data(sheets_url, range_name=range_name)
        
        print(f"📋 Retrieved {len(sheet_data)} rows")
        for i, row in enumerate(sheet_data[:5]):
            print(f"   Row {i+1}: {row}")
        
        vocabulary_entries = parser.extract_vocabulary_pairs(sheet_data)
        print(f"\n🎉 Extracted {len(vocabulary_entries)} vocabulary entries")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Main test function."""
    print("Google Sheets Processor Test")
    print("=" * 50)
    
    # Check if credentials file exists
    import os
    if not os.path.exists("credentials.json"):
        print("❌ credentials.json not found!")
        print("\nPlease ensure you have set up Google API credentials")
        return
    
    print("✅ credentials.json found")
    
    # Ask user what they want to test
    print("\nWhat would you like to test?")
    print("1. Full sheet processing")
    print("2. Specific range processing")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        success = test_google_sheets_processor()
    elif choice == "2":
        success = test_sheets_with_range()
    else:
        print("Invalid choice")
        return
    
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n❌ Tests failed")


if __name__ == "__main__":
    main()