"""
Database layer for managing processed emails, events, and LLM usage tracking
"""

import sqlite3
import json
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any


class Database:
    """
    Handles all database operations for the free food calendar agent

    Manages:
    - Processed emails tracking
    - Found events storage
    - LLM usage metrics
    - Filter performance stats
    - Food type analytics
    """

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.getenv('DATABASE_PATH', './database/events.db')

        self.db_path = db_path
        self._ensure_database_exists()

    def _ensure_database_exists(self):
        """Initialize database with schema if it doesn't exist"""
        # Create database directory if needed
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

        # Check if database needs initialization
        needs_init = not os.path.exists(self.db_path)

        if needs_init:
            print(f"📊 Initializing database at {self.db_path}")
            self.init_db()

    def init_db(self):
        """Initialize database with schema from schema.sql"""
        schema_path = os.path.join(os.path.dirname(self.db_path), 'schema.sql')

        if not os.path.exists(schema_path):
            print(f"⚠️  Schema file not found at {schema_path}")
            return False

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(schema_sql)
            conn.commit()
            print(f"✅ Database initialized successfully")
            return True
        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            return False
        finally:
            conn.close()

    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn

    # ========================================
    # PROCESSED EMAILS
    # ========================================

    def is_email_processed(self, email_id):
        """Check if email has already been processed"""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT id FROM processed_emails WHERE email_id = ?",
                (email_id,)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def save_processed_email(self, email_id, subject, sender, analysis_data=None):
        """
        Save processed email record

        Args:
            email_id: Unique email identifier
            subject: Email subject
            sender: Sender email address
            analysis_data: Dict containing filter/analysis results
        """
        conn = self._get_connection()
        try:
            # Extract analysis data
            filter_tier = analysis_data.get('filter_tier', 'unknown') if analysis_data else 'unknown'
            filter_reason = analysis_data.get('filter_reason', '') if analysis_data else ''

            gemini_is_genuine = analysis_data.get('gemini_is_genuine') if analysis_data else None
            gemini_confidence = analysis_data.get('gemini_confidence') if analysis_data else None
            gemini_reasoning = analysis_data.get('gemini_reasoning', '') if analysis_data else ''

            skipped = analysis_data.get('skipped', False) if analysis_data else False
            skip_reason = analysis_data.get('skip_reason', '') if analysis_data else ''

            conn.execute("""
                INSERT OR REPLACE INTO processed_emails
                (email_id, subject, sender, filter_tier, filter_reason,
                 gemini_is_genuine, gemini_confidence, gemini_reasoning,
                 skipped, skip_reason, processed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                email_id, subject, sender, filter_tier, filter_reason,
                gemini_is_genuine, gemini_confidence, gemini_reasoning,
                skipped, skip_reason, datetime.now()
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"❌ Error saving processed email: {e}")
            return False
        finally:
            conn.close()

    def get_recent_processed_emails(self, limit=50):
        """Get recent processed emails"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM processed_emails
                ORDER BY processed_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # ========================================
    # FOUND EVENTS
    # ========================================

    def save_found_event(self, email_id, event_data, calendar_id=None, calendar_link=None):
        """
        Save found event to database

        Args:
            email_id: Email this event was extracted from
            event_data: Dict with event details from Cohere
            calendar_id: Google Calendar event ID (if created)
            calendar_link: Google Calendar event link (if created)
        """
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO found_events
                (email_id, event_name, event_date, event_time, end_time, location,
                 food_type, cohere_confidence, cohere_reasoning, relevant_excerpt,
                 raw_cohere_response, google_calendar_event_id, google_calendar_link)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                email_id,
                event_data.get('event_name', 'Unknown Event'),
                event_data.get('date', 'unknown'),
                event_data.get('time', 'unknown'),
                event_data.get('end_time', 'unknown'),
                event_data.get('location', 'unknown'),
                event_data.get('food_type', 'food'),
                event_data.get('confidence', 0.5),
                event_data.get('reasoning', ''),
                event_data.get('relevant_excerpt', ''),
                json.dumps(event_data),
                calendar_id,
                calendar_link
            ))
            conn.commit()

            # Update food type stats
            self._update_food_type_stats(event_data.get('food_type', 'food'),
                                        event_data.get('confidence', 0.5))

            return True
        except Exception as e:
            print(f"❌ Error saving event: {e}")
            return False
        finally:
            conn.close()

    def get_recent_events(self, limit=50):
        """Get recent found events"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM found_events
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_upcoming_events(self, days=7):
        """Get upcoming events within next N days"""
        conn = self._get_connection()
        try:
            today = date.today().isoformat()
            future_date = (date.today() + timedelta(days=days)).isoformat()

            cursor = conn.execute("""
                SELECT * FROM found_events
                WHERE event_date >= ? AND event_date <= ?
                ORDER BY event_date, event_time
            """, (today, future_date))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # ========================================
    # LLM USAGE TRACKING
    # ========================================

    def save_llm_usage(self, provider, model, email_id=None, purpose='',
                      success=True, processing_time_ms=0, error_message=''):
        """
        Track LLM API usage for portfolio metrics

        Args:
            provider: 'cohere' or 'gemini'
            model: Model name
            email_id: Associated email
            purpose: 'extraction', 'filtering', 'classification'
            success: Whether call succeeded
            processing_time_ms: Processing time in milliseconds
            error_message: Error message if failed
        """
        if not os.getenv('ENABLE_LLM_TRACKING', 'true').lower() == 'true':
            return

        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO llm_usage
                (provider, model, email_id, purpose, processing_time_ms,
                 success, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (provider, model, email_id, purpose, processing_time_ms,
                  success, error_message))
            conn.commit()
        except Exception as e:
            print(f"⚠️  Error tracking LLM usage: {e}")
        finally:
            conn.close()

    def get_llm_stats(self, days=30):
        """Get LLM usage statistics for portfolio"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT
                    provider,
                    COUNT(*) as total_calls,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_calls,
                    AVG(processing_time_ms) as avg_processing_time,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
                FROM llm_usage
                WHERE called_at >= datetime('now', '-' || ? || ' days')
                GROUP BY provider
            """, (days,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_cohere_daily_usage(self):
        """Get today's Cohere usage count (for budget tracking)"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM llm_usage
                WHERE provider = 'cohere'
                  AND date(called_at) = date('now')
            """)
            result = cursor.fetchone()
            return result['count'] if result else 0
        finally:
            conn.close()

    # ========================================
    # FILTER PERFORMANCE
    # ========================================

    def save_filter_stats(self, scan_id, stats):
        """Save filter performance stats from a scan"""
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO filter_stats
                (scan_id, emails_scanned, passed_heuristic, passed_gemini,
                 processed_cohere, events_found, events_added,
                 gemini_calls, cohere_calls, scan_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scan_id,
                stats.get('emails_scanned', 0),
                stats.get('passed_tier1_heuristic', 0),
                stats.get('passed_tier2_gemini', 0),
                stats.get('processed_tier3_cohere', 0),
                stats.get('events_found', 0),
                stats.get('events_added', 0),
                stats.get('gemini_calls', 0),
                stats.get('cohere_calls', 0),
                date.today()
            ))
            conn.commit()
        except Exception as e:
            print(f"⚠️  Error saving filter stats: {e}")
        finally:
            conn.close()

    def get_filter_performance(self, days=30):
        """Get filter performance over time"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT
                    scan_date,
                    SUM(emails_scanned) as total_scanned,
                    SUM(passed_heuristic) as total_passed_t1,
                    SUM(passed_gemini) as total_passed_t2,
                    SUM(processed_cohere) as total_processed_t3,
                    SUM(cohere_calls) as total_cohere_calls,
                    SUM(events_found) as total_events
                FROM filter_stats
                WHERE scan_date >= date('now', '-' || ? || ' days')
                GROUP BY scan_date
                ORDER BY scan_date DESC
            """, (days,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # ========================================
    # FOOD TYPE ANALYTICS
    # ========================================

    def _update_food_type_stats(self, food_type, confidence):
        """Update food type statistics"""
        conn = self._get_connection()
        try:
            # Check if exists
            cursor = conn.execute(
                "SELECT count, total_confidence FROM food_type_stats WHERE food_type = ?",
                (food_type,)
            )
            result = cursor.fetchone()

            if result:
                new_count = result['count'] + 1
                new_total = result['total_confidence'] + confidence
                new_avg = new_total / new_count

                conn.execute("""
                    UPDATE food_type_stats
                    SET count = ?, total_confidence = ?, avg_confidence = ?, last_seen = ?
                    WHERE food_type = ?
                """, (new_count, new_total, new_avg, datetime.now(), food_type))
            else:
                conn.execute("""
                    INSERT INTO food_type_stats
                    (food_type, count, total_confidence, avg_confidence)
                    VALUES (?, 1, ?, ?)
                """, (food_type, confidence, confidence))

            conn.commit()
        except Exception as e:
            print(f"⚠️  Error updating food type stats: {e}")
        finally:
            conn.close()

    def get_food_type_stats(self):
        """Get food type distribution"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM food_type_stats
                ORDER BY count DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # ========================================
    # GENERAL STATS
    # ========================================

    def get_stats(self):
        """Get overall statistics"""
        conn = self._get_connection()
        try:
            stats = {}

            # Total processed emails
            cursor = conn.execute("SELECT COUNT(*) as count FROM processed_emails")
            stats['total_emails_processed'] = cursor.fetchone()['count']

            # Total events found
            cursor = conn.execute("SELECT COUNT(*) as count FROM found_events")
            stats['total_events_found'] = cursor.fetchone()['count']

            # Events added to calendar
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM found_events
                WHERE google_calendar_event_id IS NOT NULL
            """)
            stats['events_in_calendar'] = cursor.fetchone()['count']

            # Average confidence
            cursor = conn.execute("""
                SELECT AVG(cohere_confidence) as avg_conf FROM found_events
            """)
            result = cursor.fetchone()
            stats['avg_confidence'] = round(result['avg_conf'], 2) if result['avg_conf'] else 0

            # Today's Cohere usage
            stats['cohere_calls_today'] = self.get_cohere_daily_usage()

            return stats
        finally:
            conn.close()
