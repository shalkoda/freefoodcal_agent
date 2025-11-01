"""
🌟 COHERE SHOWCASE FOR INTERNSHIP APPLICATION

Demonstrates:
- Advanced prompt engineering for structured extraction
- Handling of ambiguous natural language (relative dates)
- JSON output parsing with error handling
- Production-ready LLM integration

Used for: Extracting structured event data from unstructured email text
Model: command-r-plus (best for extraction tasks)
"""

import cohere
import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class CohereEventExtractor:
    """
    🔵 PRIMARY LLM INTEGRATION - Cohere Event Extraction

    Extracts structured event data from unstructured email text using
    Cohere's command-r-plus model.

    This is the showcase component for the internship application.
    """

    def __init__(self):
        api_key = os.getenv('COHERE_API_KEY')
        if not api_key:
            raise ValueError("COHERE_API_KEY not found in environment variables")

        self.client = cohere.Client(api_key)
        # Updated to use command-r7b-12-2024 (command-r and command-r-plus were deprecated Sept 2025)
        self.model = os.getenv('COHERE_MODEL', 'command-r7b-12-2024')
        self.temperature = float(os.getenv('COHERE_TEMPERATURE', 0.3))
        self.max_tokens = int(os.getenv('COHERE_MAX_TOKENS', 1500))

        # Track usage for portfolio metrics
        self.total_calls = 0
        self.successful_extractions = 0
        
        # Rate limiting for Trial keys (10 calls/minute)
        self.last_call_time = 0
        self.min_call_interval = 6.0  # Minimum 6 seconds between calls (10 calls/min = 6 sec/call)

    def extract_events(self, email_content, email_date=None, email_subject=None):
        """
        🔥 PRIMARY COHERE INTEGRATION

        Extract structured event data using Cohere's command-r-plus model.

        This showcases:
        - Context-aware prompting (includes today's date for relative date parsing)
        - Few-shot learning examples in prompt
        - Robust JSON parsing
        - Confidence scoring

        Args:
            email_content: Raw email body
            email_date: Reference date for relative date parsing
            email_subject: Email subject line (important for event detection)

        Returns:
            {
                'has_food_event': bool,
                'events': [
                    {
                        'event_name': str,
                        'date': str (YYYY-MM-DD),
                        'time': str (HH:MM),
                        'end_time': str,
                        'location': str,
                        'food_type': str,
                        'confidence': float,
                        'reasoning': str
                    }
                ],
                'metadata': {
                    'model': str,
                    'processing_time': float
                }
            }
        """

        self.total_calls += 1
        start_time = datetime.now()

        if not email_content or len(email_content.strip()) < 10:
            return self._empty_result()

        today = email_date or datetime.now()
        prompt = self._build_extraction_prompt(email_content, today, email_subject)

        try:
            # Rate limiting for Trial keys (10 calls/minute)
            # Wait if needed to avoid 429 errors
            current_time = time.time()
            time_since_last_call = current_time - self.last_call_time
            if time_since_last_call < self.min_call_interval:
                wait_time = self.min_call_interval - time_since_last_call
                print(f"    ⏳ Rate limiting: waiting {wait_time:.1f}s to avoid 429 errors...")
                time.sleep(wait_time)
            
            # 🔥 COHERE API CALL
            self.last_call_time = time.time()
            response = self.client.chat(
                message=prompt,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            # Parse response
            if not response or not hasattr(response, 'text') or not response.text:
                return self._empty_result(error="Empty response from Cohere API")
            
            # Log response for debugging (first 200 chars)
            response_text = response.text.strip()
            if len(response_text) > 200:
                print(f"    📝 Cohere response preview: {response_text[:200]}...")
            else:
                print(f"    📝 Cohere response: {response_text}")
            
            result = self._parse_response(response_text)

            # Post-process events
            for event in result.get('events', []):
                self._normalize_event(event, today)

            # Add metadata for portfolio/analysis
            result['metadata'] = {
                'model': self.model,
                'processing_time': (datetime.now() - start_time).total_seconds()
            }

            if result.get('has_food_event'):
                self.successful_extractions += 1

            return result

        except Exception as e:
            error_str = str(e)
            # Check for rate limiting (429 errors)
            if '429' in error_str or 'rate limit' in error_str.lower() or 'Trial key' in error_str:
                print(f"❌ Cohere rate limit error: Trial keys limited to 10 calls/minute")
                print(f"   Waiting 60 seconds before next attempt...")
                time.sleep(60)  # Wait 1 minute before next call
                # Try once more after waiting
                try:
                    self.last_call_time = time.time()
                    response = self.client.chat(
                        message=prompt,
                        model=self.model,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens
                    )
                    # Continue with normal processing
                    if not response or not hasattr(response, 'text') or not response.text:
                        return self._empty_result(error="Empty response from Cohere API after retry")
                    response_text = response.text.strip()
                    result = self._parse_response(response_text)
                    for event in result.get('events', []):
                        self._normalize_event(event, today)
                    result['metadata'] = {
                        'model': self.model,
                        'processing_time': (datetime.now() - start_time).total_seconds()
                    }
                    if result.get('has_food_event'):
                        self.successful_extractions += 1
                    return result
                except Exception as e2:
                    print(f"❌ Cohere API error after retry: {e2}")
                    return self._empty_result(error=f"Rate limited and retry failed: {str(e2)}")
            else:
                print(f"❌ Cohere API error: {e}")
                return self._empty_result(error=str(e))

    def _build_extraction_prompt(self, email_content, today_date, email_subject=None):
        """
        🎨 PROMPT ENGINEERING SHOWCASE

        This prompt demonstrates:
        - Clear task definition
        - Contextual information (current date)
        - Few-shot examples
        - Structured output specification
        - Edge case handling
        """

        today_str = today_date.strftime('%Y-%m-%d')
        tomorrow = (today_date + timedelta(days=1)).strftime('%Y-%m-%d')
        day_name = today_date.strftime('%A')

        # Calculate next week dates for examples
        days_until_monday = (7 - today_date.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = (today_date + timedelta(days=days_until_monday)).strftime('%Y-%m-%d')

        # Include subject in prompt if available (critical for "Coffee Social" detection)
        subject_section = ""
        subject_instructions = ""
        if email_subject:
            subject_section = f"\nEMAIL SUBJECT: {email_subject}\n\n"
            subject_instructions = "\n⚠️  CRITICAL: Check the EMAIL SUBJECT above - it often contains the event name (e.g., 'CS CARES Coffee Social', 'WIE Coffee Chat', 'Coffee Social', 'Pizza Party', 'Halloween Party').\n\n🎯 EVENT NAME EXTRACTION RULES:\n- If the subject contains an event name like 'WIE Coffee Chat', 'CS CARES Coffee Social', 'Coffee Social', use that EXACT name as event_name\n- If the subject contains 'Coffee Chat' or 'Coffee Social', extract that as the event name (e.g., 'WIE Coffee Chat')\n- If the subject contains a party name like 'Halloween Party', use that as the event name\n- If the subject contains a food event name, prioritize it over other text in the body\n- If the subject contains 'Coffee' + 'Chat' or 'Coffee' + 'Social', combine them as the event name\n\nIf the subject contains 'Coffee Social' or 'Coffee Hour' or 'Coffee Chat', it is ALWAYS a food event with coffee provided.\n"
            # Note: Subject often contains critical info like "Coffee Social", "Coffee Chat", "Pizza Party", etc.

        prompt = f"""You are an AI assistant specialized in extracting event information from emails.

CONTEXT:
- Today is {today_str} ({day_name})
- You're looking for events that mention FREE FOOD, catering, meals, refreshments, coffee, snacks, or any consumables provided

{subject_section}{subject_instructions}EMAIL TO ANALYZE:
```
{email_content[:3000]}
```

TASK:
Extract ALL events where food, drinks, coffee, snacks, refreshments, or catering is provided. Return ONLY valid JSON.

CRITICAL RULES - These are ALWAYS food events:
- "Coffee Social" = FOOD EVENT (coffee is provided at social events)
- "CS CARES Coffee Social" = FOOD EVENT (coffee provided - use this EXACT name from subject)
- "Coffee Hour" = FOOD EVENT (coffee provided)
- "Coffee & Donuts" = FOOD EVENT (coffee and donuts provided)
- Any event with "Coffee" in the title = FOOD EVENT (coffee is a consumable)
- Any event with "Social" in the title that mentions coffee/food = FOOD EVENT
- "Lunch Meeting" = FOOD EVENT (lunch provided)
- "Pizza Party" = FOOD EVENT (pizza provided)
- "Party" with treats = FOOD EVENT
- Any event with explicit time/location + food/drinks = FOOD EVENT
- Refreshments, snacks, beverages = FOOD EVENT

EXAMPLES OF FOOD EVENTS:
- "WIE Coffee Chat" at 3pm = coffee/food provided (use "WIE Coffee Chat" as event_name, NOT other text from body)
- "CS CARES Coffee Social" at 4pm = coffee provided (use "CS CARES Coffee Social" as event_name)
- "Coffee Social" = coffee provided
- "Team Lunch" = lunch provided
- "Pizza Party" = pizza provided
- "Halloween Party" with treats = food provided

OUTPUT FORMAT:
{{
  "has_food_event": true,
  "events": [
    {{
      "event_name": "WIE Coffee Chat",
      "date": "2025-11-07",
      "time": "15:00",
      "end_time": "16:30",
      "location": "210 Engineering Hall",
      "food_type": "coffee",
      "confidence": 0.95,
      "reasoning": "Subject contains 'WIE Coffee Chat' - extract this exact event name. Coffee and food provided."
    }}
  ]
}}

CRITICAL: When extracting event_name:
- If subject contains event name like "WIE Coffee Chat", "CS CARES Coffee Social", use that EXACT name
- If subject has "Coffee Chat" or "Coffee Social", extract the full event name from subject (e.g., "WIE Coffee Chat" not just "Coffee Chat")
- If subject has "Halloween Party" or "Pizza Party", use that as event_name
- Prioritize subject line event names over generic descriptions in the body

EXAMPLE FOR COFFEE SOCIAL:
If email title contains "Coffee Social" or "Coffee Hour":
- has_food_event: true
- food_type: "coffee"
- confidence: 0.9-1.0 (high confidence because coffee is implicit in the title)

EXTRACTION RULES:

1. DATE PARSING (convert relative → absolute):
   - "tomorrow" → {tomorrow}
   - "next Monday" → {next_monday}
   - "this Friday" → calculate from {today_str}
   - "Nov 15" → 2025-11-15 (assume current year if not specified)
   - "11/15" → 2025-11-15

2. TIME PARSING (convert to 24-hour HH:MM):
   - "2pm" → "14:00"
   - "noon" → "12:00"
   - "2:30 PM" → "14:30"
   - "14:00" → "14:00"
   - If end_time not mentioned, add 1 hour to start

3. FOOD TYPE CLASSIFICATION:
   - Extract specific: pizza, tacos, sandwiches, breakfast, lunch, dinner, snacks, coffee, donuts, bbq, refreshments, beverages
   - "Coffee Social" → food_type: "coffee"
   - "Coffee & Donuts" → food_type: "coffee"
   - Any social event with refreshments → food_type: "refreshments" or "snacks"
   - Generic fallback: "catering" or "food"

4. CONFIDENCE SCORING:
   - 0.9-1.0: Explicit food mention + complete details (date, time, location)
   - 0.7-0.9: Clear food mention + most details
   - 0.5-0.7: Implied food or missing some details
   - <0.5: Don't include (too uncertain)

5. REASONING:
   - Include brief quote from email justifying extraction
   - Explain confidence score
   - Example: "Email states 'free pizza at 2pm' with specific room number"

6. If NO food events found:
   {{"has_food_event": false, "events": []}}

7. For missing info, use "unknown" (not null or empty string)

8. ONLY extract events with food. Ignore:
   - Events without food/drinks/refreshments mention
   - "Bring your own lunch" (no free food)
   - Past events
   - Cancelled events
   
9. EVENT NAME EXTRACTION (CRITICAL):
   - If EMAIL SUBJECT contains an event name like "WIE Coffee Chat", "CS CARES Coffee Social", use that EXACT name
   - DO NOT extract generic descriptions from body text if subject has a specific event name
   - Example: Subject "The WIE Buzz 10-31-25" with content mentioning "WIE Coffee Chat" → event_name: "WIE Coffee Chat" (NOT "Fireside chat with..." or "The WIE Buzz")
   - Example: Subject "Smile Halloween Party" → event_name: "Smile Halloween Party" (NOT generic party description)
   - Always prioritize the subject line event name over body text descriptions
   - Extract the FULL event name: "WIE Coffee Chat" not just "Coffee Chat"

10. INCLUDE these as food events (these are ALWAYS food events):
   - "WIE Coffee Chat" (coffee/food provided)
   - "Coffee Social" (coffee is ALWAYS provided at coffee socials)
   - "CS CARES Coffee Social" (coffee is provided)
   - "Coffee Hour" (coffee is provided)
   - Any event with "Coffee" in the title (coffee is a consumable)
   - Any "Social" event that mentions coffee/food/beverages
   - Events with "coffee", "snacks", "refreshments", "beverages" in the title or description
   - If title contains "Coffee" + "Social" or "Coffee" + "Chat" = HIGH CONFIDENCE (0.9-1.0) food event

Return ONLY the JSON object, no markdown formatting or extra text."""

        return prompt

    def _parse_response(self, response_text):
        """
        Robust JSON parsing with fallbacks

        Handles:
        - Direct JSON
        - JSON in markdown code blocks
        - JSON with extra text
        - Malformed JSON recovery
        """
        
        # Clean the response text
        response_text = response_text.strip()
        
        # Remove any leading/trailing text that's not JSON
        # Try direct JSON parse first
        try:
            result = json.loads(response_text)
            print(f"    ✅ JSON parsed successfully (direct)")
            return result
        except json.JSONDecodeError as e:
            print(f"    ⚠️  Direct JSON parse failed, trying alternatives...")

        # Try extracting from markdown code blocks
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding any JSON object in the text (improved regex)
        # Match from first { to last }
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Try more aggressive extraction - find largest JSON-like structure
        try:
            # Find all potential JSON objects
            json_pattern = r'\{(?:[^{}]|\{[^{}]*\})*\}'
            matches = re.findall(json_pattern, response_text, re.DOTALL)
            for match_text in reversed(matches):  # Try largest first
                try:
                    result = json.loads(match_text)
                    if 'has_food_event' in result or 'events' in result:
                        return result
                except json.JSONDecodeError:
                    continue
        except:
            pass

        # Last resort: try to extract and repair common issues
        try:
            # Remove common non-JSON prefixes/suffixes
            cleaned = re.sub(r'^[^{]*', '', response_text)
            cleaned = re.sub(r'[^}]*$', '', cleaned)
            if cleaned:
                return json.loads(cleaned)
        except:
            pass

        # Log the problematic response for debugging
        print(f"⚠️  Could not parse Cohere response. First 500 chars: {response_text[:500]}")
        return self._empty_result(error=f"Could not parse JSON from response. Response length: {len(response_text)}")

    def _normalize_event(self, event, reference_date):
        """
        Validate and normalize event data

        Ensures:
        - All required fields exist
        - Confidence is a float
        - Times are properly formatted
        """

        required_fields = ['event_name', 'date', 'time', 'location', 'food_type', 'confidence']

        for field in required_fields:
            if field not in event:
                event[field] = 'unknown'

        # Ensure confidence is float
        try:
            event['confidence'] = float(event['confidence'])
        except (ValueError, TypeError):
            event['confidence'] = 0.5

        # Set default end_time if missing
        if 'end_time' not in event or event['end_time'] == 'unknown':
            if event['time'] != 'unknown':
                try:
                    start = datetime.strptime(event['time'], '%H:%M')
                    end = start + timedelta(hours=1)
                    event['end_time'] = end.strftime('%H:%M')
                except:
                    event['end_time'] = 'unknown'

        # Ensure reasoning exists
        if 'reasoning' not in event:
            event['reasoning'] = 'Extracted from email content'

        return event

    def _empty_result(self, error=None):
        """Return empty result with consistent structure"""
        result = {
            'has_food_event': False,
            'events': []
        }
        if error:
            result['error'] = error
        return result

    def get_usage_stats(self):
        """
        📊 Track usage for portfolio

        Show in your internship application:
        - Total API calls made
        - Success rate
        - Demonstrates monitoring/optimization awareness
        """
        return {
            'total_cohere_calls': self.total_calls,
            'successful_extractions': self.successful_extractions,
            'success_rate': self.successful_extractions / self.total_calls if self.total_calls > 0 else 0
        }
