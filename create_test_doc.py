#!/usr/bin/env python3
"""
Helper script to create a test Google Doc with vocabulary table.
"""

def create_test_doc_instructions():
    """Print instructions for creating a test document."""
    
    print("📝 Creating a Test Google Doc")
    print("=" * 40)
    print()
    print("1. Go to https://docs.google.com/")
    print("2. Create a new document")
    print("3. Insert a table (Insert > Table > 2x4 or larger)")
    print("4. Fill it with this sample data:")
    print()
    print("┌─────────────┬─────────────┐")
    print("│ English     │ Cantonese   │")
    print("├─────────────┼─────────────┤")
    print("│ hello       │ 你好        │")
    print("│ goodbye     │ 再見        │")
    print("│ thank you   │ 謝謝        │")
    print("│ please      │ 請          │")
    print("│ excuse me   │ 唔好意思    │")
    print("│ yes         │ 係          │")
    print("│ no          │ 唔係        │")
    print("│ water       │ 水          │")
    print("│ food        │ 食物        │")
    print("│ good        │ 好          │")
    print("└─────────────┴─────────────┘")
    print()
    print("5. Share the document:")
    print("   - Click 'Share' button")
    print("   - Make sure your Google account has access")
    print("   - Copy the document URL")
    print()
    print("6. Run the test script with the URL")
    print()
    print("Alternative: You can also test with any existing Google Doc")
    print("that contains a table with English-Cantonese vocabulary pairs.")


if __name__ == "__main__":
    create_test_doc_instructions()