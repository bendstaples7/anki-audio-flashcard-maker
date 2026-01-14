#!/usr/bin/env python3
"""
Real-world test script for Google Docs processor.
"""

import sys
from cantonese_anki_generator.processors import GoogleDocsParser, GoogleDocsAuthenticator


def test_google_docs_processor():
    """Test the Google Docs processor with a real document."""
    
    print("🔧 Testing Google Docs Processor")
    print("=" * 50)
    
    # Get document URL from user
    doc_url = input("Enter Google Docs URL: ").strip()
    
    if not doc_url:
        print("❌ No URL provided")
        return False
    
    try:
        print("\n📋 Step 1: Initializing authenticator...")
        authenticator = GoogleDocsAuthenticator()
        
        print("📋 Step 2: Initializing parser...")
        parser = GoogleDocsParser(authenticator)
        
        print("📋 Step 3: Extracting document ID...")
        doc_id = parser.extract_document_id(doc_url)
        print(f"   Document ID: {doc_id}")
        
        print("📋 Step 4: Authenticating with Google...")
        if not authenticator.authenticate():
            print("❌ Authentication failed")
            return False
        print("   ✅ Authentication successful")
        
        print("📋 Step 5: Retrieving document...")
        document = parser.retrieve_document(doc_url)
        print(f"   ✅ Document retrieved (title: {document.get('title', 'Unknown')})")
        
        print("📋 Step 6: Finding tables...")
        tables = parser.find_tables(document)
        print(f"   Found {len(tables)} table(s)")
        
        if not tables:
            print("❌ No tables found in document")
            return False
        
        print("📋 Step 7: Identifying vocabulary table...")
        vocabulary_table = parser.identify_vocabulary_table(tables)
        
        if vocabulary_table is None:
            print("❌ No vocabulary table identified")
            # Show what tables were found
            for i, table in enumerate(tables):
                parsed = parser.parse_table_structure(table)
                print(f"   Table {i+1}: {len(parsed)} rows, {max(len(row) for row in parsed) if parsed else 0} columns")
                if parsed and len(parsed) > 0:
                    print(f"   Sample row: {parsed[0][:2]}")  # Show first 2 columns of first row
            return False
        
        print(f"   ✅ Vocabulary table identified ({len(vocabulary_table)} rows)")
        
        print("📋 Step 8: Extracting vocabulary pairs...")
        vocabulary_entries = parser.extract_vocabulary_pairs(vocabulary_table)
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


def test_authentication_only():
    """Test just the authentication flow."""
    print("🔐 Testing Authentication Only")
    print("=" * 40)
    
    try:
        authenticator = GoogleDocsAuthenticator()
        
        print("📋 Attempting authentication...")
        if authenticator.authenticate():
            print("✅ Authentication successful!")
            
            print("📋 Testing connection...")
            if authenticator.test_connection():
                print("✅ Connection test successful!")
            else:
                print("❌ Connection test failed")
                assert False, "Connection test failed"
        else:
            print("❌ Authentication failed")
            assert False, "Authentication failed"
            
    except Exception as e:
        print(f"❌ Error: {e}")
        assert False, f"Authentication test failed: {e}"


def main():
    """Main test function."""
    print("Google Docs Processor Test")
    print("=" * 50)
    
    # Check if credentials file exists
    import os
    if not os.path.exists("credentials.json"):
        print("❌ credentials.json not found!")
        print("\nTo set up credentials:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project and enable Google Docs API")
        print("3. Create OAuth 2.0 credentials for desktop application")
        print("4. Download and save as 'credentials.json' in this directory")
        return
    
    print("✅ credentials.json found")
    
    # Ask user what they want to test
    print("\nWhat would you like to test?")
    print("1. Authentication only")
    print("2. Full document processing")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        success = test_authentication_only()
    elif choice == "2":
        success = test_google_docs_processor()
    else:
        print("Invalid choice")
        return
    
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n❌ Tests failed")


if __name__ == "__main__":
    main()