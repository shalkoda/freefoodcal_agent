"""
Gemini-based semantic filtering (Tier 2)
Lightweight semantic filter using Gemini Flash (free tier)

Purpose: Reduce Cohere API calls by filtering obvious spam/marketing
This allows us to reserve Cohere for genuine event extraction
"""

import google.generativeai as genai
import os


class GeminiSemanticFilter:
    """
    Lightweight semantic filter using Gemini Flash (free tier)

    Purpose: Reduce Cohere API calls by filtering obvious spam/marketing
    This allows us to reserve Cohere for genuine event extraction
    """

    def __init__(self):
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")

        genai.configure(api_key=api_key)
        # Use gemini-1.5-flash (not -latest suffix) - this is the correct model name
        model_name = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
        try:
            self.model = genai.GenerativeModel(model_name)
        except Exception as e:
            # Fallback to gemini-pro if flash model not available
            if 'flash' in model_name.lower():
                print(f"  ⚠️  Model {model_name} not available, falling back to gemini-pro")
                try:
                    self.model = genai.GenerativeModel('gemini-pro')
                except Exception as e2:
                    print(f"  ⚠️  Gemini-pro also failed: {e2}, bypassing Gemini filter")
                    # Set a flag to bypass Gemini if model initialization fails
                    self.model = None
            else:
                raise

    def is_genuine_event(self, email_content, sender_email="", email_subject=""):
        """
        Quick check: Is this worth sending to Cohere?

        Args:
            email_content: Email body text
            sender_email: Sender's email address
            email_subject: Email subject line (important for event detection)

        Returns:
            bool: True if likely a genuine event, False if spam/marketing
        """

        # Include subject in prompt - critical for "Coffee Social" detection
        subject_section = f"Subject: {email_subject}\n\n" if email_subject else ""
        
        prompt = f"""Is this email a genuine invitation to an internal event where FOOD/DRINKS/REFRESHMENTS are PROVIDED? Answer YES or NO only.

Sender: {sender_email}
{subject_section}Email: {email_content[:800]}

CRITICAL: Only answer YES if:
- Food/drinks/refreshments are explicitly mentioned as being provided (NOT "bring your own lunch")
- Event has food-related keywords: coffee, lunch, pizza, snacks, refreshments, drinks, goodies, treats, catering, etc.
- Specific event with food: "Coffee Social", "Coffee Chat", "Halloween Party" (with treats), "Pizza Party", etc.

Genuine food event indicators:
- Internal sender (@company domain, @edu, @gov)
- Specific date/time/location
- Food explicitly mentioned as provided (coffee, lunch, pizza, snacks, refreshments, drinks, goodies, treats)
- Event title suggests food: "Coffee Social", "Coffee Chat", "Halloween Party", "Pizza Party", etc.
- Language indicating food provided: "we provide", "grab a bite", "treats", "goodies", "refreshments"

CRITICAL EXAMPLES:
- "Coffee Social" = YES (coffee is provided)
- "Coffee Chat" = YES (coffee/food typically provided)
- "Halloween Party" with "treats" or "goodies" = YES
- "Team Lunch" = YES (lunch provided)
- "Pizza Party" = YES (pizza provided)

Spam indicators:
- External sender
- Marketing language
- No food mentioned
- "Bring your own lunch" = NO (no food provided)
- Generic promotional content without food

Answer (YES/NO):"""

        # Bypass Gemini if model initialization failed
        if self.model is None:
            print(f"  ⚠️  Gemini model not initialized - bypassing filter (allowing to Cohere)")
            return True
            
        try:
            response = self.model.generate_content(prompt)
            answer = response.text.strip().lower()
            return 'yes' in answer
        except Exception as e:
            print(f"  ⚠️  Gemini API error: {e}")
            # If API key is invalid, allow emails through to Cohere (bypass filter)
            # This allows testing when Gemini isn't configured
            if 'API key' in str(e) or 'API_KEY' in str(e) or 'API_KEY_INVALID' in str(e):
                print(f"  ⚠️  Gemini API key invalid - bypassing filter (allowing to Cohere)")
                # Return True to allow emails through when Gemini isn't available
                # This prevents blocking all emails when Gemini API key isn't set
                return True
            # For other errors, default to True (process) to avoid false negatives
            return True

    def classify_sender(self, sender_email):
        """
        Classify sender type for better filtering

        Args:
            sender_email: Sender's email address

        Returns:
            str: 'internal', 'external_trusted', 'marketing', 'unknown'
        """

        prompt = f"""Classify this email sender. Answer with ONE word only: internal, external_trusted, marketing, or unknown.

Sender: {sender_email}

Categories:
- internal: Company employee, @edu, @gov domains
- external_trusted: Known service providers, event platforms
- marketing: Promotional, newsletter, no-reply addresses
- unknown: Cannot determine

Answer:"""

        try:
            response = self.model.generate_content(prompt)
            classification = response.text.strip().lower()

            valid_types = ['internal', 'external_trusted', 'marketing', 'unknown']
            for vtype in valid_types:
                if vtype in classification:
                    return vtype

            return 'unknown'
        except Exception as e:
            print(f"  ⚠️  Gemini API error: {e}")
            return 'unknown'

    def extract_food_type(self, text):
        """
        Quick LLM call to classify specific food type
        Useful for analytics and categorization

        Args:
            text: Text mentioning food

        Returns:
            str: Food type category
        """

        prompt = f"""What specific type of food is mentioned in this text?

Text: {text[:200]}

Return ONLY one of: pizza, tacos, sandwiches, breakfast, lunch, dinner, snacks, coffee, donuts, bbq, catering, other

Answer:"""

        try:
            response = self.model.generate_content(prompt)
            food_type = response.text.strip().lower()

            # Validate response
            valid_types = ['pizza', 'tacos', 'sandwiches', 'breakfast', 'lunch', 'dinner',
                          'snacks', 'coffee', 'donuts', 'bbq', 'catering', 'other']

            for vtype in valid_types:
                if vtype in food_type:
                    return vtype

            return 'other'
        except Exception as e:
            print(f"  ⚠️  Gemini API error: {e}")
            return 'other'

    def analyze_sentiment(self, email_content):
        """
        Analyze the tone/sentiment of the email

        Args:
            email_content: Email body text

        Returns:
            dict: {
                'sentiment': 'casual' | 'formal' | 'promotional',
                'confidence': float
            }
        """

        prompt = f"""Analyze the tone of this email. Answer in this exact format:
TONE: casual/formal/promotional
CONFIDENCE: 0.0-1.0

Email: {email_content[:500]}

Tone definitions:
- casual: Informal, team communication, friendly
- formal: Official company communication, professional
- promotional: Marketing, sales, advertising

Answer:"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip().lower()

            sentiment = 'formal'  # default
            confidence = 0.5

            if 'casual' in text:
                sentiment = 'casual'
            elif 'promotional' in text:
                sentiment = 'promotional'

            # Try to extract confidence
            import re
            conf_match = re.search(r'confidence:\s*(0?\.\d+|1\.0)', text)
            if conf_match:
                confidence = float(conf_match.group(1))

            return {
                'sentiment': sentiment,
                'confidence': confidence
            }
        except Exception as e:
            print(f"  ⚠️  Gemini API error: {e}")
            return {'sentiment': 'formal', 'confidence': 0.5}
