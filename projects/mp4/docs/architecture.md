# Project 6 — System Architecture

## 1. Project Overview

Collaborative Fog Computing for Real-Time Predictive Maintenance, Dynamic Task Scheduling and Fault-Tolerant Industrial Monitoring.

The system monitors 12 industrial machines distributed across three zones (A, B and C). Each zone has one Fog node responsible for local data processing.

## 2. Global Architecture

### Mini-Project 1 — Industrial Simulation and AI
- Simulates 12 industrial machines.
- Generates sensor data every second.
- Publishes data through MQTT.
- Detects anomalies and predicts machine failures.

### Mini-Project 2 — Collaborative Fog Computing
- Manages three Fog nodes (A, B and C).
- Processes data close to industrial machines.
- Monitors CPU, RAM, workload and node availability.
- Migrates eligible non-critical tasks.
- Recovers tasks when a Fog node fails.

### Mini-Project 3 — Cloud Backend
- Uses FastAPI and PostgreSQL.
- Stores machines, measurements, predictions, alerts and Fog events.
- Provides REST APIs for external applications.
- Provides historical data and global analytics.

### Mini-Project 4 — Dashboard, Observability and DevOps
- Uses React for the monitoring interface.
- Displays machine conditions and predictions.
- Displays alerts and Fog node status.
- Displays task scheduling and recovery information.
- Uses Prometheus and Grafana for observability.
- Uses Docker and Docker Compose for deployment.
- Uses GitHub Actions for automated testing and CI.

## 3. Communication Flow

1. Industrial machines generate sensor measurements.
2. Mini-Project 1 publishes measurements using MQTT.
3. Mini-Project 2 processes measurements locally on Fog nodes.
4. Fog nodes send relevant results to the Cloud backend.
5. Mini-Project 3 stores and exposes the information through REST APIs.
6. Mini-Project 4 retrieves information and displays it.
7. Prometheus collects monitoring metrics and Grafana visualizes them.

## 4. Dashboard Scope

The dashboard contains:
- Factory overview.
- Machine monitoring.
- Predictions and alerts.
- Fog node monitoring.
- Task scheduling and migration.
- Historical statistics.

## 5. Important Integration Rule

The dashboard communicates with the Cloud backend through documented REST APIs.

The frontend must not access PostgreSQL directly.

API endpoints, MQTT topics and JSON formats will be finalized with the other mini-project teams before integration.