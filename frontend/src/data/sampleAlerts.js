
const sampleAlerts = [
  {
    alert_id: "ALT001",
    user_id: "EMP014",
    risk_level: "HIGH",
    risk_score: 72,
    reason: "Behavior deviates from the user's normal baseline.",
    evidence: "Unusual access to a sensitive resource.",
  },
  {
    alert_id: "ALT002",
    user_id: "EMP027",
    risk_level: "MEDIUM",
    risk_score: 48,
    reason: "Activity differs from the user's peer group.",
    evidence: "Higher-than-usual download volume.",
  },
  {
    alert_id: "ALT003",
    user_id: "EMP031",
    risk_level: "CRITICAL",
    risk_score: 86,
    reason: "Multiple contextual risk indicators detected.",
    evidence:
      "Sensitive resource access combined with an external destination.",
  },
];

export default sampleAlerts;
