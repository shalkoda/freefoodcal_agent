"""
Centralized configuration management
Loads environment variables and provides defaults
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration"""

    # LLM APIs
    COHERE_API_KEY = os.getenv('COHERE_API_KEY')
    COHERE_MODEL = os.getenv('COHERE_MODEL', 'command-r-plus')
    COHERE_TEMPERATURE = float(os.getenv('COHERE_TEMPERATURE', 0.3))
    COHERE_MAX_TOKENS = int(os.getenv('COHERE_MAX_TOKENS', 1500))

    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')

    # Microsoft Azure (Outlook)
    MICROSOFT_CLIENT_ID = os.getenv('MICROSOFT_CLIENT_ID')
    MICROSOFT_CLIENT_SECRET = os.getenv('MICROSOFT_CLIENT_SECRET')
    MICROSOFT_TENANT_ID = os.getenv('MICROSOFT_TENANT_ID', 'common')
    MICROSOFT_REDIRECT_URI = os.getenv('MICROSOFT_REDIRECT_URI', 'http://localhost:5000/auth/microsoft/callback')

    # Google Calendar
    GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/callback')

    # Scanning Configuration
    EMAIL_SEARCH_QUERY = os.getenv('EMAIL_SEARCH_QUERY', 'food OR pizza OR lunch OR breakfast OR dinner OR snacks OR catering')
    SCAN_INTERVAL_HOURS = int(os.getenv('SCAN_INTERVAL_HOURS', 6))
    MAX_EMAILS_PER_SCAN = int(os.getenv('MAX_EMAILS_PER_SCAN', 50))

    # Filtering Configuration
    COHERE_DAILY_BUDGET = int(os.getenv('COHERE_DAILY_BUDGET', 15))
    MIN_CONFIDENCE_THRESHOLD = float(os.getenv('MIN_CONFIDENCE_THRESHOLD', 0.7))
    GEMINI_FILTER_THRESHOLD = float(os.getenv('GEMINI_FILTER_THRESHOLD', 0.5))

    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', './database/events.db')

    # Flask
    FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))

    # Analytics & Monitoring
    ENABLE_LLM_TRACKING = os.getenv('ENABLE_LLM_TRACKING', 'true').lower() == 'true'
    LOG_LLM_RESPONSES = os.getenv('LOG_LLM_RESPONSES', 'false').lower() == 'true'

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required = {
            'COHERE_API_KEY': cls.COHERE_API_KEY,
            'GOOGLE_API_KEY': cls.GOOGLE_API_KEY,
        }

        missing = [key for key, value in required.items() if not value]

        if missing:
            print(f"⚠️  Warning: Missing required configuration: {', '.join(missing)}")
            print(f"   Please set these in your .env file")
            return False

        return True
