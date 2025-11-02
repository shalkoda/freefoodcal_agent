# 🔧 API Setup Instructions

Complete guide for setting up all required APIs and credentials for the Free Food Calendar Agent.

## 📋 Required APIs

- **Cohere API** (Primary event extraction)
- **Google/Gemini API** (Spam filtering)
- **Microsoft Azure** (Outlook/Email)
- **Google Cloud** (Calendar)

---

## 3.1 Cohere API (Primary Event Extraction)

1. Go to [https://dashboard.cohere.com](https://dashboard.cohere.com)
2. Sign up / log in
3. Create an API key (free tier: 1000 calls/month)
4. Copy the key

## 3.2 Google/Gemini API (Spam Filtering)

1. Go to [https://ai.google.dev](https://ai.google.dev)
2. Get API key for Gemini (free tier: 1500 requests/day)
3. Copy the key

## 3.3 Microsoft Azure (Outlook/Email)

1. Go to [Azure Portal](https://portal.azure.com)
2. Register a new app in "App registrations"
3. Add redirect URI: `http://localhost:5050/auth/microsoft/callback`
4. Grant permissions: `User.Read`, `Mail.Read`
5. Generate client secret
6. Copy Client ID, Client Secret, Tenant ID

## 3.4 Google Cloud (Calendar)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable Google Calendar API
4. Create OAuth 2.0 credentials
5. Add redirect URI: `http://localhost:5050/auth/google/callback`
6. Download `credentials.json`
7. Place in project root
8. **Add Test Users** (Required for testing mode):
   - Go to "APIs & Services" → "OAuth consent screen"
   - Scroll to "Test users" section
   - Click "+ ADD USERS"
   - Add your email address (e.g., `your-email@gmail.com`)
   - Click "ADD"
   - **Note**: Your app is in testing mode, so only added test users can authenticate. To allow all users, publish your app (may require Google verification).

---

## 📝 Configuration

After setting up all APIs, add your credentials to `.env` file:

```bash
# LLM APIs
COHERE_API_KEY=your_cohere_key_here
GOOGLE_API_KEY=your_gemini_key_here

# Microsoft (Outlook)
MICROSOFT_CLIENT_ID=your_client_id
MICROSOFT_CLIENT_SECRET=your_client_secret
MICROSOFT_TENANT_ID=common
MICROSOFT_REDIRECT_URI=http://localhost:5050/auth/microsoft/callback

# Google Calendar
GOOGLE_REDIRECT_URI=http://localhost:5050/auth/google/callback

# Configuration
COHERE_DAILY_BUDGET=10000  # Increased for more processing
MAX_EMAILS_PER_SCAN=500    # Scan more emails per run
MIN_CONFIDENCE_THRESHOLD=0.7
COHERE_RATE_LIMIT_INTERVAL=6.0  # Rate limit in seconds (default: 6.0 for safety)
```

---

## 🔒 Security Notes

- **Never commit** `credentials.json` or `.env` files to git
- These files are already in `.gitignore` for your protection
- If credentials are accidentally committed, regenerate them immediately
- Use `credentials.json.example` as a template for the structure only

---

## ❓ Troubleshooting

### "COHERE_API_KEY not found"
- Check your `.env` file exists and contains `COHERE_API_KEY=your_key`
- Make sure you've run `python run.py setup` to load configuration

### "credentials.json file not found or empty"
- Download `credentials.json` from Google Cloud Console
- Place it in the project root directory
- Ensure the file is not empty (0 bytes)

### "Error 403: access_denied" (Google Calendar)
- Your app is in testing mode - add yourself as a test user (see step 8 above)
- Go to Google Cloud Console → OAuth consent screen → Test users
- Add your email address to the test users list

### "Authentication failed"
- Check OAuth redirect URIs match exactly in both your app registration and `.env` file
- For Google: Must be exactly `http://localhost:5050/auth/google/callback`
- For Microsoft: Must be exactly `http://localhost:5050/auth/microsoft/callback`
- Ensure API permissions are granted in Azure Portal / Google Cloud Console

