# API Contract — Project 6

## 1. Purpose

This document defines the information required by the Industrial Monitoring Dashboard (Mini-Project 4).

The following structures are provisional examples. They must be validated against the real APIs provided by Mini-Project 3.

## 2. Required Data

### Machines
- machine_id
- name
- zone
- machine_type
- status

### Measurements
- machine_id
- timestamp
- temperature
- vibration
- pressure
- speed
- current
- power
- frequency

### Predictions
- machine_id
- timestamp
- risk_score
- anomaly_detected
- predicted_fault

### Alerts
- alert_id
- machine_id
- severity
- message
- timestamp
- status

### Fog Nodes
- fog_id
- zone
- status
- cpu_usage
- ram_usage
- queue_length
- last_heartbeat

### Task Events
- task_id
- source_fog
- destination_fog
- priority
- status
- timestamp

## 3. Expected Backend API Resources

Provisional endpoint names:

- GET /api/machines
- GET /api/machines/{machine_id}/measurements/latest
- GET /api/predictions
- GET /api/alerts
- GET /api/fog-nodes
- GET /api/tasks
- GET /api/kpis

## 4. Integration Rules

- The backend is the main data source for the dashboard.
- The frontend uses HTTP REST requests.
- JSON is the expected response format.
- API endpoints and field names must be confirmed with Mini-Project 3.
- The dashboard must handle loading, empty and error states.
- Mock data will be used during frontend development.