# 🍕 Free Food Event Finder

AI agent that scans your Gmail for events with free food and adds them to Google Calendar.

## Features
- 🤖 Cohere AI extracts event details from emails
- 📧 Gmail API integration
- 📅 Automatic Google Calendar event creation
- 💾 SQLite state management (no duplicate processing)
- 🌐 Web dashboard for monitoring
- ⏰ Scheduled scanning (configurable interval)

## Setup Instructions

### 1. Prerequisites
- Python 3.9+
- Google Cloud account
- Cohere API key

### 2. Google Cloud Setup
[Detailed steps for OAuth credentials]

### 3. Cohere API Key
[Where to get it]

### 4. Installation
\`\`\`bash
git clone <repo>
cd cf_ai_food_event_finder
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
\`\`\`

### 5. Database Setup
\`\`\`bash
python -c "from src.database import init_db; init_db()"
\`\`\`

### 6. Run
\`\`\`bash
python run.py
# Open http://localhost:5000
\`\`\`

## How It Works
[Architecture diagram and flow explanation]

## Configuration
[Environment variables explained]

## Troubleshooting
[Common issues and solutions]

## Future Improvements
- Webhook-based real-time processing
- Support for Outlook/Exchange
- ML model for food type classification
- Mobile app
