# MP1 - Industrial simulation and predictive maintenance

MP1 owns the industrial telemetry simulator, scenario data, feature generation, model training and evaluation, and MQTT publishing.

- `simulator/`: Python package, datasets, model artifacts, documentation, and tests.
- `industrial-simulation/`: supporting industrial assets, contracts, and source documentation.

Start with the README inside each subproject. MP2 consumes MP1 telemetry and, where configured, its model artifact; keep those message and model paths aligned with the MP2 compose configuration.