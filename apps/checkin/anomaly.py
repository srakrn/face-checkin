"""
Anomaly detection for check-in attempts.

A check-in is flagged as anomalous when its IP address or user agent differs
from the most common value seen across *all* check-ins in the same session.
This can indicate a request was not submitted from the legitimate kiosk device.
"""

from collections import Counter


def detect_anomalies(checkins):
    """
    Given a list of CheckIn objects (all from the same session), return a
    mapping of checkin.pk → list-of-reason-strings.  An empty list means the
    check-in looks normal.

    Args:
        checkins: iterable of CheckIn model instances

    Returns:
        dict[int, list[str]]: {checkin.pk: [reason, ...]}
    """
    checkins = list(checkins)
    if not checkins:
        return {}

    # Determine the "expected" kiosk fingerprint for this session
    ip_counts = Counter(c.ip_address for c in checkins if c.ip_address)
    ua_counts = Counter(c.user_agent for c in checkins if c.user_agent)

    dominant_ip = ip_counts.most_common(1)[0][0] if ip_counts else None
    dominant_ua = ua_counts.most_common(1)[0][0] if ua_counts else None

    result = {}
    for checkin in checkins:
        reasons = []
        if dominant_ip and checkin.ip_address and checkin.ip_address != dominant_ip:
            reasons.append(f"IP {checkin.ip_address} differs from expected {dominant_ip}")
        if dominant_ua and checkin.user_agent and checkin.user_agent != dominant_ua:
            reasons.append("User agent differs from expected kiosk browser")
        result[checkin.pk] = reasons

    return result
