
def get_severity_from_score(risk_score: float) -> str:
    """Return the official ARGUS severity for a risk score."""

    if not 0 <= risk_score <= 100:
        raise ValueError("Risk score must be between 0 and 100")

    if risk_score <= 30:
        return "LOW"
    elif risk_score <= 60:
        return "MEDIUM"
    elif risk_score <= 80:
        return "HIGH"
    else:
        return "CRITICAL"
