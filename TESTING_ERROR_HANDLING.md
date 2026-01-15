# Testing Error Handling - Quick Guide

## Quick Start

### 1. Run Automated Tests
```bash
pytest tests/test_error_handling_web.py -v
```

This tests:
- ✅ Invalid URL formats
- ✅ Missing audio files
- ✅ Invalid audio formats
- ✅ Missing JSON data
- ✅ Non-existent sessions
- ✅ Error codes are present
- ✅ Error messages are descriptive

### 2. Manual Testing (Browser)

#### Start the Server
```bash
python cantonese_anki_generator/web/run.py
```

Then open: `http://localhost:3000`

---

## Manual Test Scenarios

### ✅ Test 1: Invalid URL
1. Enter: `https://example.com/not-a-doc`
2. **Expected**: Red error message appears
3. **Expected**: "Process" button stays disabled

### ✅ Test 2: Wrong File Type
1. Try to upload a `.txt` or `.pdf` file
2. **Expected**: Error: "Unsupported format..."

### ✅ Test 3: Network Retry
1. Open DevTools (F12) → Network tab
2. Enable "Offline" mode
3. Try to upload
4. **Expected**: Error with "Retry" button
5. Disable "Offline" mode
6. Click "Retry"
7. **Expected**: Upload succeeds

### ✅ Test 4: Session Not Found
1. In browser, go to: `http://localhost:3000?session=invalid_id_123`
2. **Expected**: Error: "Session not found..."
3. **Expected**: Retry button appears

### ✅ Test 5: Large File
1. Try to upload a file > 500MB
2. **Expected**: Error about file size limit

---

## Testing with Browser DevTools

### Simulate Network Errors
1. Open DevTools (F12)
2. Go to **Network** tab
3. Enable **Throttling** dropdown
4. Select **Offline** to simulate no connection
5. Or select **Slow 3G** to simulate timeout

### View Error Responses
1. Open DevTools (F12)
2. Go to **Network** tab
3. Perform an action (upload, process, etc.)
4. Click on the request
5. View **Response** tab to see error details

### Check Console Logs
1. Open DevTools (F12)
2. Go to **Console** tab
3. Look for error messages and retry attempts
4. Should see: "Request failed, retrying in Xms..."

---

## Backend Error Logs

### View Server Logs
When running the server, watch the console for:
- `WARNING` - Validation failures
- `ERROR` - Processing errors
- `INFO` - Successful operations

Example log output:
```
WARNING  cantonese_anki_generator.web.api:api.py:187 URL validation failed: Invalid URL format
ERROR    cantonese_anki_generator.web.api:api.py:783 Processing failed: File not found
INFO     cantonese_anki_generator.web.api:api.py:750 Processing complete: session_id=abc123
```

---

## Testing Retry Functionality

### Test Automatic Retry
1. Start server
2. Open browser to `http://localhost:3000`
3. Open DevTools Console
4. Upload a file with network throttling enabled
5. Watch console for retry messages:
   ```
   Request failed, retrying in 1000ms... (attempt 1/2)
   Request failed, retrying in 2000ms... (attempt 2/2)
   ```

### Test Manual Retry Button
1. Cause an error (e.g., invalid URL)
2. Error toast appears with "Retry" button
3. Fix the issue (e.g., correct the URL)
4. Click "Retry" button
5. Operation should succeed

---

## Expected Error Messages

### Frontend Errors
- ❌ "Network error - please check your internet connection"
- ❌ "Request timeout - please check your connection and try again"
- ❌ "Failed to connect to server. Please check your connection."
- ❌ "Invalid URL format. Please provide a valid Google Docs or Sheets URL"
- ❌ "Unsupported format. Please select an MP3, WAV, or M4A file."
- ❌ "File too large (X MB). Maximum size is 500MB."

### Backend Errors
- ❌ "Document not found. Please check the URL and ensure the document exists."
- ❌ "Access denied. Please ensure the document is shared with your Google account..."
- ❌ "Audio file not found. Please upload the file again."
- ❌ "Session not found: {id}. It may have expired or been deleted."
- ❌ "Failed to authenticate with Google API. Please ensure credentials are configured correctly."

---

## Error Codes Reference

All errors include an `error_code` field for programmatic handling:

| Code | Meaning | HTTP Status |
|------|---------|-------------|
| `FILE_TOO_LARGE` | Upload exceeds 500MB | 413 |
| `INVALID_URL` | URL format invalid | 400 |
| `MISSING_AUDIO` | No audio file provided | 400 |
| `INVALID_AUDIO` | Bad audio format/size | 400 |
| `SAVE_FAILED` | File save error | 500 |
| `UPLOAD_ERROR` | General upload failure | 500 |
| `MISSING_DATA` | No request body | 400 |
| `INVALID_JSON` | Malformed JSON | 400 |
| `MISSING_FIELDS` | Required fields missing | 400 |
| `FILE_NOT_FOUND` | File doesn't exist | 404 |
| `PROCESSING_ERROR` | Processing failed | 500 |
| `SESSION_NOT_FOUND` | Session doesn't exist | 404 |
| `INTERNAL_ERROR` | Unexpected server error | 500 |

---

## Troubleshooting

### Tests Fail Due to Google Auth
Some tests may fail if Google credentials aren't configured. This is expected in test environments. The error handling still works correctly - it returns appropriate error messages.

### Server Won't Start
- Check if port 3000 is already in use
- Try: `python cantonese_anki_generator/web/run.py`
- Or specify different port via `FLASK_PORT` environment variable

### Can't See Retry Buttons
- Make sure you're using a modern browser (Chrome, Firefox, Edge)
- Check browser console for JavaScript errors
- Ensure `app.js` loaded correctly (check Network tab)

---

## Success Criteria

✅ All automated tests pass (or fail only due to missing Google credentials)
✅ Error messages are clear and actionable
✅ Retry buttons appear for recoverable errors
✅ Network errors trigger automatic retry with exponential backoff
✅ All errors include error codes
✅ Server logs show detailed error information
✅ No sensitive information exposed in error messages

---

## Next Steps

After testing, consider:
1. Add error tracking (e.g., Sentry)
2. Monitor error rates in production
3. Add user feedback mechanism
4. Create error analytics dashboard
5. Add circuit breaker for repeated failures
