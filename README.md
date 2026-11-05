
# Collaborative Fog Computing

## Project Description

A distributed Fog Computing architecture for
industrial IoT monitoring and fault-tolerant
dynamic task scheduling.

## Main Components

- Fog A: Production Zone A
- Fog B: Production Zone B
- Fog C: Production Zone C
- Dynamic Scheduler
- MQTT Communication
- Resource Monitoring
- Fault Tolerance and Recovery

## Technologies

- Python 3.12
- FastAPI
- MQTT / Mosquitto
- Docker
- Docker Compose
- Prometheus
- pytest

## Project Structure

- fog_nodes/: Independent Fog services
- scheduler/: Dynamic task scheduling
- shared/: Common data models
- mqtt/: MQTT communication
- tests/: Automated tests
- monitoring/: Monitoring configuration
- docs/: Technical documentation
