"""
Main FoodEventAgent - Orchestrates the full pipeline

3-Tier Filtering Architecture:
1. Tier 1: Rule-based heuristics (free, instant)
2. Tier 2: Gemini semantic filtering (free, fast)
3. Tier 3: Cohere event extraction (free tier budget)
"""

import os
import uuid
from datetime import datetime

from src.outlook_client import OutlookClient
from src.cohere_parser import CohereEventExtractor
from src.gemini_filter import GeminiSemanticFilter
from src.filters import should_process_with_llm, has_food_keywords
from src.database import Database


class FoodEventAgent:
    """
    🎯 MAIN ORCHESTRATOR - 3-Tier Filtering Pipeline

    Coordinates:
    - Email fetching (Outlook)
    - LLM analysis (Cohere + Gemini)
    - Calendar creation (Google)
    - State management (Database)
    """

    def __init__(self):
        self.outlook = OutlookClient()
        self.gemini_filter = GeminiSemanticFilter()
        self.cohere_extractor = CohereEventExtractor()  # 🌟 Showcase
        self.db = Database()

        # Budget control
        self.cohere_daily_budget = int(os.getenv('COHERE_DAILY_BUDGET', 15))
        self.min_confidence = float(os.getenv('MIN_CONFIDENCE_THRESHOLD', 0.7))

    def scan_emails(self, calendar_client=None):
        """
        🔥 MAIN SCANNING FUNCTION

        Implements 3-tier filtering to stay within Cohere free tier
        Returns detailed stats for portfolio/monitoring

        Args:
            calendar_client: GoogleCalendarClient instance (optional)

        Returns:
            dict: Scan results and statistics
        """

        scan_id = str(uuid.uuid4())

        results = {
            'scan_id': scan_id,
            'timestamp': datetime.now().isoformat(),

            # Volume stats
            'emails_scanned': 0,
            'passed_tier1_heuristic': 0,
            'passed_tier2_gemini': 0,
            'processed_tier3_cohere': 0,

            # Filtering reasons
            'filtered_tier1': 0,  # Heuristic
            'filtered_tier2': 0,  # Gemini
            'skipped_budget': 0,  # Cohere budget exhausted

            # Results
            'events_found': 0,
            'events_added': 0,

            # API usage
            'gemini_calls': 0,
            'cohere_calls': 0,

            # Errors
            'errors': []
        }

        try:
            # Fetch emails
            search_query = os.getenv('EMAIL_SEARCH_QUERY',
                'food OR pizza OR lunch OR breakfast')
            max_emails = int(os.getenv('MAX_EMAILS_PER_SCAN', 50))

            print(f"\n🔍 Searching emails with query: {search_query}")
            emails = self.outlook.search_emails(search_query, max_results=max_emails)
            print(f"📧 Fetched {len(emails)} emails")

            # Check today's Cohere usage
            cohere_used_today = self.db.get_cohere_daily_usage()
            cohere_budget_remaining = max(0, self.cohere_daily_budget - cohere_used_today)

            print(f"🔵 Cohere budget: {cohere_budget_remaining}/{self.cohere_daily_budget} remaining today")

            for email in emails:
                results['emails_scanned'] += 1

                # Skip if already processed, but allow re-processing if needed
                if self.db.is_email_processed(email['id']):
                    # Allow re-processing emails that were filtered at Tier 2 (Gemini)
                    # since Gemini was bypassing incorrectly before
                    # This helps when we fix the filtering logic
                    subject = email.get('subject', '') or ''
                    if any(keyword in subject.lower() for keyword in ['coffee', 'social', 'pizza', 'lunch', 'food']):
                        print(f"    🔄 Re-processing email that might have been incorrectly filtered...")
                        # Continue processing - clear old record will happen in save_processed_email
                    else:
                        continue

                # Get full content
                content = self.outlook.get_email_content(email['id'])
                if not content:
                    continue

                subject = email.get('subject', 'No Subject') or 'No Subject'
                print(f"\n  📨 [{results['emails_scanned']}] {subject[:60]}...")

                # ========================================
                # TIER 1: HEURISTIC FILTER (Free, instant)
                # ========================================
                should_process, tier1_reason, tier1_score = should_process_with_llm(
                    content, email['sender']
                )

                if not should_process:
                    print(f"    ❌ Tier 1 filtered: {tier1_reason}")
                    results['filtered_tier1'] += 1

                    self.db.save_processed_email(
                        email['id'], email.get('subject', 'No Subject'), email.get('sender', 'Unknown'),
                        analysis_data={
                            'filter_tier': 'heuristic',
                            'filter_reason': tier1_reason,
                            'heuristic_score': tier1_score
                        }
                    )
                    continue

                results['passed_tier1_heuristic'] += 1
                print(f"    ✅ Tier 1 passed (score: {tier1_score:.2f})")

                # ========================================
                # TIER 2: GEMINI FILTER (Free, semantic)
                # ========================================
                print(f"    🟢 Tier 2: Gemini semantic check...")
                is_genuine = self.gemini_filter.is_genuine_event(content, email['sender'])
                results['gemini_calls'] += 1

                if not is_genuine:
                    print(f"    ❌ Tier 2 filtered: Not a genuine event")
                    results['filtered_tier2'] += 1

                    self.db.save_processed_email(
                        email['id'], email.get('subject', 'No Subject'), email.get('sender', 'Unknown'),
                        analysis_data={
                            'filter_tier': 'gemini',
                            'filter_reason': 'Not genuine event',
                            'gemini_is_genuine': False
                        }
                    )

                    # Track Gemini usage
                    self.db.save_llm_usage(
                        provider='gemini',
                        model='gemini-1.5-flash',
                        email_id=email['id'],
                        purpose='filtering',
                        success=True
                    )
                    continue

                results['passed_tier2_gemini'] += 1
                print(f"    ✅ Tier 2 passed (genuine event detected)")

                # Track Gemini usage
                self.db.save_llm_usage(
                    provider='gemini',
                    model='gemini-1.5-flash',
                    email_id=email['id'],
                    purpose='filtering',
                    success=True
                )

                # ========================================
                # TIER 3: COHERE EXTRACTION (Budget-controlled)
                # ========================================

                # Check budget
                if cohere_budget_remaining <= 0:
                    print(f"    ⚠️  Tier 3 skipped: Daily Cohere budget exhausted")
                    results['skipped_budget'] += 1
                    continue

                print(f"    🔵 Tier 3: Cohere extraction (budget: {cohere_budget_remaining} remaining)...")

                extraction_start = datetime.now()
                extraction = self.cohere_extractor.extract_events(
                    content,
                    email_date=datetime.now()
                )
                processing_time = (datetime.now() - extraction_start).total_seconds() * 1000

                cohere_budget_remaining -= 1
                results['cohere_calls'] += 1
                results['processed_tier3_cohere'] += 1

                # Track LLM usage
                # Use model name from config
                model_name = os.getenv('COHERE_MODEL', 'command-r7b-12-2024')
                self.db.save_llm_usage(
                    provider='cohere',
                    model=model_name,
                    email_id=email['id'],
                    purpose='extraction',
                    success=extraction and not extraction.get('error'),
                    processing_time_ms=int(processing_time)
                )

                # Process results
                # Check if extraction is valid and has events
                if not extraction:
                    print(f"    ⚠️  Extraction returned None or empty")
                elif extraction.get('error'):
                    print(f"    ❌ Extraction error: {extraction.get('error')}")
                elif extraction.get('has_food_event'):
                    events = extraction.get('events', [])
                    if not events:
                        print(f"    ℹ️  No food events extracted")
                    else:
                        print(f"    ✅ Found {len(events)} event(s)")

                        for event in events:
                            if event.get('confidence', 0) >= self.min_confidence:
                                results['events_found'] += 1

                                # Create calendar event if client provided
                                if calendar_client and event.get('date') != 'unknown':
                                    try:
                                        # Check duplicate
                                        if calendar_client.check_duplicate(event.get('event_name', ''), event.get('date', '')):
                                            print(f"       ⏭️  Duplicate: {event.get('event_name', 'Unknown')}")
                                            continue

                                        # Create event
                                        cal_event = calendar_client.create_event(
                                            event_name=event.get('event_name', 'Food Event'),
                                            date=event.get('date', 'unknown'),
                                            time=event.get('time', '12:00'),
                                            end_time=event.get('end_time', 'unknown'),
                                            location=event.get('location', 'TBD'),
                                            food_type=event.get('food_type', 'food'),
                                            description=f"🍕 Free Food!\n\nFood: {event.get('food_type', 'food')}\nConfidence: {event.get('confidence', 0):.0%}\n\nExtracted by Cohere AI"
                                        )

                                        # Save to database
                                        self.db.save_found_event(
                                            email_id=email['id'],
                                            event_data=event,
                                            calendar_id=cal_event.get('event_id'),
                                            calendar_link=cal_event.get('html_link')
                                        )

                                        results['events_added'] += 1
                                        print(f"       ✅ Added to calendar: {event.get('event_name', 'Food Event')}")

                                    except Exception as e:
                                        print(f"       ❌ Calendar error: {e}")
                                        results['errors'].append({
                                            'email_id': email['id'],
                                            'event': event.get('event_name', 'Unknown'),
                                            'error': str(e)
                                        })
                                else:
                                    # No calendar client - just save event data
                                    self.db.save_found_event(
                                        email_id=email['id'],
                                        event_data=event,
                                        calendar_id=None,
                                        calendar_link=None
                                    )
                                    print(f"       💾 Saved event (no calendar): {event.get('event_name', 'Unknown')}")
                            else:
                                print(f"       ⚠️  Low confidence ({event.get('confidence', 0):.2f}): {event.get('event_name', 'Unknown')}")
                else:
                    print(f"    ℹ️  No food events extracted")

                # Save processed email
                try:
                    events_count = len(extraction.get('events', [])) if extraction else 0
                    self.db.save_processed_email(
                        email['id'], email.get('subject', 'No Subject'), email.get('sender', 'Unknown'),
                        analysis_data={
                            'filter_tier': 'passed_all',
                            'cohere_extraction': extraction if extraction else {},
                            'events_found': events_count
                        }
                    )
                except Exception as e:
                    print(f"    ⚠️  Error saving processed email: {e}")
                    results['errors'].append({
                        'email_id': email['id'],
                        'step': 'save_processed_email',
                        'error': str(e)
                    })

            # Save scan stats
            try:
                self.db.save_filter_stats(scan_id, results)
            except Exception as e:
                print(f"⚠️  Error saving scan stats: {e}")
                results['errors'].append({
                    'step': 'save_filter_stats',
                    'error': str(e)
                })

            # Print summary
            self._print_summary(results)

            return results

        except Exception as e:
            import traceback
            print(f"❌ Scan error: {e}")
            print(f"   Traceback: {traceback.format_exc()}")
            results['errors'].append({'general_error': str(e), 'traceback': traceback.format_exc()})
            return results

    def _print_summary(self, results):
        """Print scan summary"""
        print(f"\n{'='*60}")
        print(f"📊 SCAN SUMMARY")
        print(f"{'='*60}")
        print(f"Emails scanned:      {results['emails_scanned']}")
        print(f"  ✅ Passed Tier 1:  {results['passed_tier1_heuristic']}")
        print(f"  ✅ Passed Tier 2:  {results['passed_tier2_gemini']}")
        print(f"  🔵 Processed T3:   {results['processed_tier3_cohere']}")
        print(f"\nFiltered:")
        print(f"  ❌ Tier 1 (spam):  {results['filtered_tier1']}")
        print(f"  ❌ Tier 2 (fake):  {results['filtered_tier2']}")
        print(f"  ⚠️  Budget limit:  {results['skipped_budget']}")
        print(f"\nAPI Usage:")
        print(f"  🟢 Gemini calls:   {results['gemini_calls']} (free)")
        print(f"  🔵 Cohere calls:   {results['cohere_calls']} / {self.cohere_daily_budget} budget")
        print(f"\nResults:")
        print(f"  🍕 Events found:   {results['events_found']}")
        print(f"  📅 Events added:   {results['events_added']}")
        if results['errors']:
            print(f"  ❌ Errors:         {len(results['errors'])}")
        print(f"{'='*60}\n")

    def get_stats(self):
        """Get overall statistics"""
        return self.db.get_stats()

    def get_llm_stats(self, days=30):
        """Get LLM usage statistics"""
        return self.db.get_llm_stats(days)

    def get_filter_performance(self, days=30):
        """Get filter performance over time"""
        return self.db.get_filter_performance(days)

    def get_cohere_usage_stats(self):
        """Get Cohere extractor usage stats"""
        return self.cohere_extractor.get_usage_stats()
