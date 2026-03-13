## ADDED Requirements

### Requirement: Console serving endpoint
The system SHALL expose `GET /console` returning the management console single-page application as an HTML response. The endpoint SHALL be implemented in `src/market_data/api/rest/console.py` and included in the FastAPI app.

#### Scenario: Console page served
- **WHEN** `GET /console` is requested
- **THEN** HTTP 200 is returned with `Content-Type: text/html` containing the full console HTML
