# Anomaly Detection for Check-ins

## Overview

Detect potential kiosk impersonation by flagging check-ins that use different IP addresses or user agents than the majority of check-ins in a session.

## Detection Logic

For each session:

1. **Identify the "normal" kiosk fingerprint:**
   - Find the most common IP address across all check-ins
   - Find the most common user agent across all check-ins

2. **Flag anomalies:**
   - Mark any check-in as anomalous if its IP address differs from the most common IP **OR** its user agent differs from the most common user agent

## Implementation Plan

### 1. Anomaly Detection Function

Create [`apps/checkin/anomaly.py`](apps/checkin/anomaly.py):

```python
def detect_anomalies(checkins):
    """
    Detect anomalous check-ins based on IP and user agent.
    
    Returns:
        dict: {checkin_id: {"is_anomaly": bool, "reasons": [str]}}
    """
    # Count IP addresses and user agents
    # Find most common of each
    # Flag check-ins that differ from the majority
```

### 2. Update Report View

Modify [`apps/sessions/views.py:session_report_page`](apps/sessions/views.py:104):
- Call anomaly detection function
- Pass anomaly data to template context

### 3. Update Report Template

Modify [`templates/sessions/report.html`](templates/sessions/report.html):
- Add "Anomaly" column to check-in table
- Show warning badge for anomalous check-ins
- Add summary card showing anomaly count
- Display IP and user agent in table (optional, for transparency)

### 4. Update CSV Export

Modify [`apps/sessions/views.py:session_report_csv`](apps/sessions/views.py:123):
- Add "Anomaly" column
- Add "IP Address" and "User Agent" columns

## Visual Design

**Anomaly indicator:**
- 🚨 Warning badge (orange/yellow) for anomalous check-ins
- Tooltip explaining why it's flagged (different IP/UA)

**Summary card:**
- Show count of anomalous check-ins
- Highlight if anomaly rate is high (e.g., >10%)

## Edge Cases

- **Empty IP/UA:** Treat as distinct value (not anomalous by default)
- **Tie in most common:** Pick the first one alphabetically
- **Single check-in:** Cannot determine anomaly (no majority)
- **All different:** All flagged as anomalous (legitimate scenario for distributed kiosks)

## Future Enhancements (out of scope)

- Time-based anomaly detection (check-ins outside normal hours)
- Velocity checks (same face from multiple IPs in short time)
- Geolocation-based checks (if IP geolocation is available)
