#!/usr/bin/env python3
"""
Helper script instructions for creating a test Google Sheet.
"""

def create_test_sheet_instructions():
    """Print instructions for creating a test Google Sheet."""
    
    print("📊 Creating a Test Google Sheet")
    print("=" * 40)
    print()
    print("1. Go to https://sheets.google.com/")
    print("2. Create a new spreadsheet")
    print("3. In cell A1, type 'English'")
    print("4. In cell B1, type 'Cantonese'")
    print("5. Fill in the vocabulary data:")
    print()
    print("   A          B")
    print("1  English    Cantonese")
    print("2  hello      你好")
    print("3  goodbye    再見")
    print("4  thank you  謝謝")
    print("5  please     請")
    print("6  excuse me  唔好意思")
    print("7  yes        係")
    print("8  no         唔係")
    print("9  water      水")
    print("10 food       食物")
    print("11 good       好")
    print()
    print("6. Share the spreadsheet:")
    print("   - Click 'Share' button")
    print("   - Make sure your Google account has access")
    print("   - Copy the spreadsheet URL")
    print()
    print("7. Run: python test_google_sheets_real.py")
    print()
    print("💡 Pro tip: You can copy a table from your Google Doc")
    print("   and paste it directly into the Google Sheet!")
    print()
    print("💡 For single lessons: Create separate sheets within")
    print("   the same spreadsheet (Sheet1, Sheet2, etc.) or")
    print("   use different spreadsheets for each lesson.")


if __name__ == "__main__":
    create_test_sheet_instructions()