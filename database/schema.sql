-- ============================================
-- PROCESSED EMAILS
-- ============================================
CREATE TABLE IF NOT EXISTS processed_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT UNIQUE NOT NULL,
    subject TEXT,
    sender TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Filter tracking
    filter_tier TEXT,  -- 'heuristic', 'gemini', 'cohere', 'passed'
    filter_reason TEXT,  -- Why filtered/passed

    -- Gemini analysis (if reached Tier 2)
    gemini_is_genuine BOOLEAN,
    gemini_confidence REAL,
    gemini_reasoning TEXT,

    -- Processing flags
    skipped BOOLEAN DEFAULT 0,
    skip_reason TEXT,

    UNIQUE(email_id)
);

-- ============================================
-- FOUND EVENTS
-- ============================================
CREATE TABLE IF NOT EXISTS found_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT NOT NULL,

    -- Event details
    event_name TEXT NOT NULL,
    event_date TEXT,  -- YYYY-MM-DD
    event_time TEXT,  -- HH:MM
    end_time TEXT,
    location TEXT,
    food_type TEXT,

    -- Cohere extraction results
    cohere_confidence REAL,  -- 0.0-1.0
    cohere_reasoning TEXT,
    relevant_excerpt TEXT,
    raw_cohere_response TEXT,  -- Full JSON for analysis

    -- Calendar integration
    google_calendar_event_id TEXT,
    google_calendar_link TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (email_id) REFERENCES processed_emails(email_id)
);

-- ============================================
-- LLM USAGE TRACKING (For Portfolio!)
-- ============================================
CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Which LLM was called
    provider TEXT NOT NULL,  -- 'cohere' or 'gemini'
    model TEXT,  -- 'command-r-plus', 'gemini-1.5-flash'

    -- Usage details
    email_id TEXT,
    purpose TEXT,  

    -- Request details
    input_tokens INTEGER,
    output_tokens INTEGER,
    processing_time_ms INTEGER,

    -- Response metadata
    success BOOLEAN,
    error_message TEXT,

    -- Timestamp
    called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (email_id) REFERENCES processed_emails(email_id)
);

-- ============================================
-- FILTER PERFORMANCE TRACKING
-- ============================================
CREATE TABLE IF NOT EXISTS filter_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT,  -- Groups stats from one scan

    -- Volume at each tier
    emails_scanned INTEGER,
    passed_heuristic INTEGER,
    passed_gemini INTEGER,
    processed_cohere INTEGER,

    -- Results
    events_found INTEGER,
    events_added INTEGER,

    -- API usage
    gemini_calls INTEGER,
    cohere_calls INTEGER,

    -- Timestamp
    scan_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- FOOD TYPE ANALYTICS
-- ============================================
CREATE TABLE IF NOT EXISTS food_type_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food_type TEXT UNIQUE NOT NULL,
    count INTEGER DEFAULT 1,
    total_confidence REAL,  -- Sum of confidence scores
    avg_confidence REAL,     -- Average confidence
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- LLM FEEDBACK (For Improvement)
-- ============================================
CREATE TABLE IF NOT EXISTS llm_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER,
    email_id TEXT,

    -- User feedback
    feedback_type TEXT,  -- 'correct', 'incorrect', 'missed_event', 'false_positive'
    feedback_notes TEXT,

    -- Original LLM output (for retraining data)
    original_cohere_confidence REAL,
    should_have_been_confidence REAL,
    original_extraction TEXT,  -- JSON
    corrected_extraction TEXT,  -- JSON

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (event_id) REFERENCES found_events(id),
    FOREIGN KEY (email_id) REFERENCES processed_emails(email_id)
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================
CREATE INDEX IF NOT EXISTS idx_email_id ON processed_emails(email_id);
CREATE INDEX IF NOT EXISTS idx_event_date ON found_events(event_date);
CREATE INDEX IF NOT EXISTS idx_food_type ON found_events(food_type);
CREATE INDEX IF NOT EXISTS idx_cohere_confidence ON found_events(cohere_confidence);
CREATE INDEX IF NOT EXISTS idx_filter_tier ON processed_emails(filter_tier);

-- LLM tracking indexes
CREATE INDEX IF NOT EXISTS idx_llm_provider ON llm_usage(provider);
CREATE INDEX IF NOT EXISTS idx_llm_called_at ON llm_usage(called_at);
CREATE INDEX IF NOT EXISTS idx_scan_date ON filter_stats(scan_date);
