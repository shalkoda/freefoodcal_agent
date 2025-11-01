"""
Rule-based heuristic filters (Tier 1)
No API calls - instant, free filtering
"""

import re


def quick_spam_check(email_content, sender=""):
    """
    Fast spam detection using keywords

    Args:
        email_content: Email body text
        sender: Sender email address

    Returns:
        (is_spam: bool, reason: str)
    """
    content_lower = email_content.lower()

    # Strong spam indicators
    spam_keywords = [
        'unsubscribe', 'opt out', 'opt-out',
        'promotional', 'advertisement',
        'click here', 'buy now', 'limited time',
        'act now', 'special offer', 'discount',
        'free trial', 'no obligation'
    ]

    spam_score = sum(1 for keyword in spam_keywords if keyword in content_lower)

    if spam_score >= 3:
        return True, f"High spam score: {spam_score}"

    # Marketing email patterns
    if 'unsubscribe' in content_lower and 'http' in content_lower:
        return True, "Marketing email pattern detected"

    # Promotional sender patterns
    if sender:
        sender_lower = sender.lower()
        promotional_patterns = ['noreply', 'no-reply', 'marketing', 'promo', 'newsletter']
        if any(pattern in sender_lower for pattern in promotional_patterns):
            return True, f"Promotional sender: {sender}"

    return False, "Passed heuristic check"


def has_food_keywords(email_content):
    """
    Check if email mentions food-related terms

    Args:
        email_content: Email body text

    Returns:
        (has_food: bool, matched_keywords: list)
    """
    food_keywords = [
        'pizza', 'lunch', 'breakfast', 'dinner',
        'food', 'catering', 'snacks', 'bagels',
        'donuts', 'coffee', 'sandwiches', 'tacos',
        'bbq', 'potluck', 'refreshments', 'meal',
        'buffet', 'free food', 'provided', 'served'
    ]

    content_lower = email_content.lower()
    matched = [kw for kw in food_keywords if kw in content_lower]

    return len(matched) > 0, matched


def is_internal_sender(sender_email, company_domain=""):
    """
    Check if sender is internal (increases genuineness probability)

    Args:
        sender_email: Sender's email address
        company_domain: Your company domain (e.g., 'company.com')

    Returns:
        bool: True if likely internal sender
    """
    if not sender_email:
        return False

    sender_lower = sender_email.lower()

    # Common internal indicators
    internal_domains = ['.edu', '.gov']
    if company_domain:
        internal_domains.append(company_domain)

    for domain in internal_domains:
        if domain and domain in sender_lower:
            return True

    # No-reply or automated senders (likely not genuine events)
    if 'noreply' in sender_lower or 'no-reply' in sender_lower:
        return False

    return False


def has_event_indicators(email_content):
    """
    Check for indicators that this is a real event invitation

    Args:
        email_content: Email body text

    Returns:
        (has_indicators: bool, indicators: list)
    """
    indicators = []
    content_lower = email_content.lower()

    # Date/time indicators
    date_patterns = [
        r'tomorrow', r'today', r'this (monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
        r'next (monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
        r'\d{1,2}/\d{1,2}', r'(january|february|march|april|may|june|july|august|september|october|november|december) \d{1,2}'
    ]

    for pattern in date_patterns:
        if re.search(pattern, content_lower):
            indicators.append('date_mentioned')
            break

    # Time patterns (2pm, 14:00, etc)
    if re.search(r'\d{1,2}:\d{2}|\d{1,2}\s?(am|pm)|noon', content_lower):
        indicators.append('time_mentioned')

    # Location indicators
    location_keywords = ['room', 'building', 'floor', 'office', 'conference', 'zoom', 'meet', 'location']
    if any(kw in content_lower for kw in location_keywords):
        indicators.append('location_mentioned')

    # RSVP indicators
    rsvp_keywords = ['rsvp', 'sign up', 'register', 'reply', 'confirm attendance']
    if any(kw in content_lower for kw in rsvp_keywords):
        indicators.append('rsvp_requested')

    # Invitation language
    invitation_keywords = ['join us', 'you\'re invited', 'please join', 'welcome to']
    if any(kw in content_lower for kw in invitation_keywords):
        indicators.append('invitation_language')

    return len(indicators) > 0, indicators


def calculate_initial_score(email_content, sender=""):
    """
    Calculate a quick 0-1 score for email genuineness

    Args:
        email_content: Email body text
        sender: Sender email address

    Returns:
        float: 0.0 = definitely spam, 1.0 = likely genuine
    """
    score = 0.5  # Start neutral

    # Spam check
    is_spam, _ = quick_spam_check(email_content, sender)
    if is_spam:
        score -= 0.4

    # Food keywords
    has_food, keywords = has_food_keywords(email_content)
    if has_food:
        score += 0.2
        if len(keywords) >= 3:
            score += 0.1  # Multiple food mentions
    else:
        score -= 0.3

    # Internal sender
    if is_internal_sender(sender):
        score += 0.2

    # Event indicators
    has_indicators, indicators = has_event_indicators(email_content)
    if has_indicators:
        score += 0.1 * min(len(indicators), 3)  # Up to +0.3 for indicators

    return max(0.0, min(1.0, score))  # Clamp to 0-1


def should_process_with_llm(email_content, sender=""):
    """
    Determine if email is worth processing with LLM (Tier 2/3)

    This is the main Tier 1 filter function.

    Args:
        email_content: Email body text
        sender: Sender email address

    Returns:
        (should_process: bool, reason: str, score: float)
    """
    # Quick spam check first
    is_spam, spam_reason = quick_spam_check(email_content, sender)
    if is_spam:
        return False, spam_reason, 0.0

    # Must have food keywords
    has_food, food_kw = has_food_keywords(email_content)
    if not has_food:
        return False, "No food keywords found", 0.1

    # Calculate overall score
    score = calculate_initial_score(email_content, sender)

    # Threshold for LLM processing
    if score >= 0.3:
        return True, f"Passed heuristic (score: {score:.2f}, food: {', '.join(food_kw[:3])})", score
    else:
        return False, f"Low score: {score:.2f}", score
