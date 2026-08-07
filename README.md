# ARGUS -- Context-Aware Insider Threat Detection System

## 1. Project Overview

**ARGUS (Context-Aware Insider Threat Detection System)** is a
software-based cybersecurity project designed to identify and assess
potential insider threats within an organization.

Insider threats are particularly difficult to detect because legitimate
employees, contractors, or other authorized users already have access to
organizational systems and sensitive resources. ARGUS focuses on
analyzing user behavior together with organizational context instead of
relying only on isolated anomalies.

The system is intended to generate a **risk score for each employee**,
identify potentially suspicious activity, provide **explainable AI
recommendations**, and present risk trends through a dashboard.

## 2. Problem Statement

Organizations face increasing risks from insider threats, where
authorized users may intentionally or unintentionally misuse sensitive
data.

Existing **User Behavior Analytics (UBA)** systems primarily depend on
anomaly detection. A behavior that differs from a user's normal pattern
may therefore be flagged even when there is a legitimate reason for it.
This can result in:

-   High numbers of false positives.
-   Important threats being missed.
-   Increased workload for security analysts.
-   Difficulty understanding why an alert was generated.

ARGUS addresses this problem by combining **user behavior with
organizational context** to support more accurate and explainable
insider-threat detection.

## 3. Proposed Solution

ARGUS proposes a context-aware approach to insider threat detection.

The system analyzes relevant user activity and considers contextual
information before assigning a risk level. Instead of treating every
unusual activity as a threat, the system aims to provide a more
meaningful assessment by considering the surrounding organizational
context.

The major outputs of the proposed system are:

1.  Employee-level risk scores.
2.  Insider threat alerts.
3.  Explainable AI recommendations.
4.  Dashboard-based risk trend visualization.
5.  Reduced false positives.

## 4. Key Objectives

The main objectives of ARGUS are:

-   **Detect insider threats:** Identify potentially suspicious employee
    activities.
-   **Generate risk scores:** Assign a risk score to every employee
    based on analyzed behavior.
-   **Provide explainability:** Give understandable recommendations or
    reasons associated with detected risks.
-   **Generate alerts:** Notify security analysts about potentially
    risky activities.
-   **Visualize trends:** Provide a dashboard for monitoring employee
    risk and overall trends.
-   **Reduce false positives:** Improve detection by considering
    organizational context rather than relying only on anomalies.

## 5. System Concept

The high-level working concept of ARGUS is:

``` text
User Activity
      ↓
Data Collection
      ↓
Feature / Behavior Analysis
      ↓
Context Analysis
      ↓
Machine Learning
      ↓
Risk Score Generation
      ↓
Threat Alert + Explanation
      ↓
Security Dashboard
```

The exact implementation details and final processing pipeline are part
of the planned development of the project.

## 6. Technology Stack

The project presentation identifies the following technology areas:

  Area               Technologies
  ------------------ ---------------------
  Frontend           React, Tailwind CSS
  Backend            Python, FastAPI
  Database           PostgreSQL
  Analytics          Pandas, NumPy
  Machine Learning   Scikit-learn
  Security           JWT, bcrypt

These technologies support the development of the web dashboard, backend
services, data processing, machine-learning components, and application
security.

### Note on the current project presentation

The PPT also lists **MongoDB, Node.js, and Flask** in its software
requirements section. fileciteturn0file0L134-L143 The
technology-stack slide lists **FastAPI and PostgreSQL**.
fileciteturn0file0L115-L116 Therefore, the final implementation
stack should be confirmed by the project team before this README is
treated as the definitive technical specification.

## 7. Expected Outputs

ARGUS is expected to produce the following outputs:

### Employee Risk Score

A risk score for every employee to help indicate the relative level of
suspicious behavior.

### Explainable AI Recommendations

The system is expected to provide understandable recommendations
associated with detected risks rather than presenting only a numerical
result.

### Insider Threat Alerts

Potentially suspicious activities should generate alerts that can be
reviewed by security analysts.

### Risk Trend Dashboard

A dashboard should display relevant risk trends and provide a
centralized view for monitoring.

### Reduced False Positives

By incorporating organizational context into the detection process,
ARGUS aims to reduce unnecessary alerts caused by legitimate but unusual
behavior.

## 8. Hardware Requirements

The project presentation specifies the following hardware requirements:

-   **Processor:** Intel i5 / Ryzen 5 or above
-   **RAM:** Minimum 8 GB
-   **Recommended RAM:** 16 GB
-   **Storage:** At least 20 GB free SSD space
-   **Internet:** Required for GitHub and package installation

## 9. Software Requirements

The presentation lists:

-   Windows 11 / Ubuntu 22.04
-   Python 3.11+
-   VS Code
-   Git
-   MongoDB
-   Node.js
-   React
-   Flask
-   Chrome Browser

These are the software requirements currently documented in the project
PPT. fileciteturn0file0L134-L143

## 10. Project Development

The project follows a staged development approach beginning with problem
analysis and progressing toward implementation, machine-learning
development, testing, dashboard integration, documentation, and
presentation.

The project timeline in the PPT is planned as an **8-week mini-project
schedule**, covering activities such as:

-   Literature survey and problem analysis.
-   System and requirement design.
-   Development.
-   Machine-learning model development.
-   Testing.
-   Documentation and presentation.

## 11. Project Significance

ARGUS focuses on an important cybersecurity challenge: detecting threats
originating from users who already possess legitimate access.

The key idea is to move beyond simply asking:

> "Is this behavior unusual?"

and instead support a broader assessment based on available
organizational context.

This can help security analysts prioritize potentially important events,
understand risk indicators, and reduce time spent investigating
unnecessary alerts.

## 12. Future Scope

The current project focuses on developing the proposed context-aware
detection system and its core outputs.

Possible future extensions can be considered after the initial
implementation, such as:

-   Real-time activity monitoring.
-   Integration with SIEM platforms.
-   More advanced machine-learning techniques.
-   Cloud-based deployment.
-   Additional organizational context sources.
-   Improved predictive analytics.

These extensions are future possibilities and are not presented as
completed functionality in the current project review.

## 13. References

The project PPT references the following sources:

1.  Greitzer, F. L., & Hohimer, R. E. (2011). *Modeling Human Behavior
    to Anticipate Insider Attacks*. Journal of Strategic Security.
2.  Salem, M., Hershkop, S., & Stolfo, S. J. (2008). *A Survey of
    Insider Attack Detection Research*. Springer.
3.  Eberle, W., & Holder, L. (2009). *Insider Threat Detection Using
    Graph-Based Approaches*. IEEE.
4.  CERT Insider Threat Center, Carnegie Mellon University.
5.  MITRE ATT&CK.

## 14. Project Information

**Project:** ARGUS -- Context-Aware Insider Threat Detection System

**Problem Statement:** PSAIAC_170

**Category:** Software

**Project Review:** CSS7102 -- Mini Project Review-1

**Institution:** Presidency University

**School:** School of Artificial Intelligence and Advanced Computing

**Supervisor:** Dr. Manan Kumar Gupta

## 15. Conclusion

ARGUS is proposed as a context-aware insider threat detection system
that combines behavioral analysis with organizational context. Its
primary goal is to identify potential insider threats, provide
employee-level risk scores and explainable recommendations, generate
alerts, and visualize risk trends through a dashboard.

By focusing on context-aware analysis rather than anomaly detection
alone, ARGUS aims to support more useful threat detection and reduce
unnecessary false positives.
