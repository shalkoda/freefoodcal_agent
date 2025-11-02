# Testing Guide for Auto-Calendar Feature

## Quick Test Checklist

### 1. Database Setup
```bash
python3 run.py setup
```
✅ Should create/update database with `user_settings` table

### 2. Start the Web Server
```bash
python3 run.py web
```
✅ Server should start on `http://localhost:5000`

### 3. Test Toggle UI
- [ ] Open http://localhost:5000
- [ ] See "Auto-Calendar Settings" card
- [ ] Toggle switch is visible and clickable
- [ ] Default state should be OFF

### 4. Test Authentication Flow
- [ ] Click "Authenticate Now" (if not authenticated)
- [ ] Complete Google OAuth flow
- [ ] See success message after auth
- [ ] Status shows "✅ Google Calendar is authenticated"

### 5. Test Toggle Enable
- [ ] Turn toggle ON
- [ ] See "✅ Auto-calendar enabled" message
- [ ] Refresh page - toggle should stay ON
- [ ] Status message persists

### 6. Test Manual Scan with Auto-Calendar
- [ ] Ensure toggle is ON
- [ ] Ensure authenticated
- [ ] Click "Scan Emails Now"
- [ ] Wait for scan to complete
- [ ] Check results show "Events added: X"
- [ ] Verify events appear in Google Calendar

### 7. Test Toggle Disable
- [ ] Turn toggle OFF
- [ ] Run another scan
- [ ] Events found but NOT added to calendar
- [ ] Results show "Events added: 0"

### 8. Test Database Settings
You can verify settings are saved by checking the database:
```bash
sqlite3 database/events.db "SELECT * FROM user_settings;"
```

Should show:
```
auto_calendar_enabled|true  (or false)
```

## Expected Behavior

### When Auto-Calendar is ENABLED:
- ✅ All scans (manual and automatic) add events to Google Calendar
- ✅ Requires Google Calendar authentication
- ✅ Shows warning if not authenticated
- ✅ Events are automatically created for every free food event found

### When Auto-Calendar is DISABLED:
- ✅ Scans still find events
- ✅ Events are NOT added to Google Calendar
- ✅ No authentication required

## Troubleshooting

### Toggle doesn't save
- Check browser console for errors
- Verify `/settings` endpoint is accessible
- Check database is writable

### Authentication fails
- Check `credentials.json` exists
- Verify redirect URI matches: `http://localhost:5000/auth/google/callback`
- Check OAuth consent screen is configured

### Events not added to calendar
- Verify toggle is ON
- Verify authentication status
- Check scan results for errors
- Verify calendar API permissions

### Database errors
- Run `python3 run.py setup` to reinitialize
- Check file permissions on `database/events.db`
- Ensure schema includes `user_settings` table

## Manual API Testing

### Test GET /settings
```bash
curl http://localhost:5000/settings
```
Should return:
```json
{
  "success": true,
  "settings": {
    "auto_calendar_enabled": false,
    "auto_scan_enabled": false,
    "google_authenticated": false
  }
}
```

### Test POST /settings
```bash
curl -X POST http://localhost:5000/settings \
  -H "Content-Type: application/json" \
  -d '{"auto_calendar_enabled": true}'
```
Should return updated settings.

### Test /scan endpoint
```bash
curl -X POST http://localhost:5000/scan
```
Should return scan results with event counts.

