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
        # Updated to use command-r (command-r-plus was deprecated Sept 2025)
        self.model = os.getenv('COHERE_MODEL', 'command-r')
        self.temperature = float(os.getenv('COHERE_TEMPERATURE', 0.3))
        self.max_tokens = int(os.getenv('COHERE_MAX_TOKENS', 1500))

        # Track usage for portfolio metrics
        self.total_calls = 0
        self.successful_extractions = 0

    def extract_events(self, email_content, email_date=None):
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
        prompt = self._build_extraction_prompt(email_content, today)

        try:
            # 🔥 COHERE API CALL
            response = self.client.chat(
                message=prompt,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            # Parse response
            result = self._parse_response(response.text)

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
            print(f"❌ Cohere API error: {e}")
            return self._empty_result(error=str(e))

    def _build_extraction_prompt(self, email_content, today_date):
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

        prompt = f"""You are an AI assistant specialized in extracting event information from emails.

CONTEXT:
- Today is {today_str} ({day_name})
- You're looking for events that mention FREE FOOD, catering, or meals provided

EMAIL TO ANALYZE:
```
{email_content[:3000]}
```

TASK:
Extract ALL events where food is provided. Return ONLY valid JSON.

OUTPUT FORMAT:
{{
  "has_food_event": true,
  "events": [
    {{
      "event_name": "Weekly Team Standup",
      "date": "2025-11-15",
      "time": "14:00",
      "end_time": "15:00",
      "location": "Conference Room A",
      "food_type": "pizza",
      "confidence": 0.95,
      "reasoning": "Email explicitly states 'pizza will be provided at 2pm in Conf Room A'"
    }}
  ]
}}

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
   - Extract specific: pizza, tacos, sandwiches, breakfast, lunch, dinner, snacks, coffee, donuts, bbq
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
   - Events without food mention
   - "Bring your own lunch" (no free food)
   - Past events
   - Cancelled events

Return ONLY the JSON object, no markdown formatting or extra text."""

        return prompt

    def _parse_response(self, response_text):
        """
        Robust JSON parsing with fallbacks

        Handles:
        - Direct JSON
        - JSON in markdown code blocks
        - JSON with extra text
        """

        try:
            # Try direct JSON parse first
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try extracting from markdown code blocks
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

            # Try finding any JSON object in the text
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass

            return self._empty_result(error="Could not parse JSON from response")

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
