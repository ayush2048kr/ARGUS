# ARGUS Backend API Contract

Current contract between M3 Backend and M4 Frontend.

Base URL: `http://127.0.0.1:8000`

## Authentication

### POST /auth/register
Registers a new user. Self-registration creates the `analyst` role.

Request:
```json
{"user_id":"EMP001","password":"example-password"}
```

### POST /auth/login
Returns a JWT access token.

Request:
```json
{"user_id":"EMP001","password":"example-password"}
```

Protected requests use:
`Authorization: Bearer <JWT>`

## Dashboard

### GET /dashboard/summary
Roles: `admin`, `analyst`.
Returns `total_users`, `total_events`, `total_alerts`, and `alerts_by_severity`.

## Users

### GET /users/me
Any authenticated user can retrieve their own profile.

### GET /users/
Role: `admin`. Returns all users.

### GET /users/{user_id}
Role: `admin`. Returns one user's profile.

### PATCH /users/{user_id}/deactivate
Role: `admin`. Deactivates a user.

## Events

### GET /events/
Roles: `admin`, `analyst`. Returns stored events.

### GET /events/{event_id}
Roles: `admin`, `analyst`. Returns one event.

### GET /events/user/{user_id}
Roles: `admin`, `analyst`. Returns events for a user.

### POST /events/
Authenticated users can create an event using the ARGUS event schema.

## Risks

### GET /risks/
Roles: `admin`, `analyst`. Returns stored risk assessments.

### GET /risks/{risk_id}
Roles: `admin`, `analyst`. Returns one risk assessment.

### GET /risks/user/{user_id}
Roles: `admin`, `analyst`. Returns risks for a user.

### POST /risks/
Roles: `admin`, `analyst`. Stores a risk assessment.
Risk score fields are validated from 0 to 100.
The backend does not calculate the official risk score; that methodology belongs to the ML/risk engine.

## Alerts

### GET /alerts/
Roles: `admin`, `analyst`. Returns stored alerts.

### GET /alerts/{alert_id}
Roles: `admin`, `analyst`. Returns one alert.

### PATCH /alerts/{alert_id}/status
Roles: `admin`, `analyst`.
Query parameter: `new_status`.
Allowed values: `open`, `investigating`, `resolved`.

Example:
`PATCH /alerts/ALERT001/status?new_status=investigating`

## Integration Rules

1. React communicates with FastAPI; React must not access MongoDB directly.
2. Protected endpoints require a JWT Bearer token.
3. The frontend must not calculate the official ARGUS risk score.
4. Risk methodology belongs to the ML/risk engine.
5. `user_id`, `event_id`, `risk_id`, and `alert_id` connect investigation data.
6. This contract may evolve during M2/M4 integration.
