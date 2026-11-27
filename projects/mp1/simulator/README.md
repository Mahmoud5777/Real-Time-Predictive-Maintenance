## Usage by MP2 (inference)
```python
from src.inference import Predictor          # needs mp1-simulator on PYTHONPATH
p = Predictor()                              # loads models/mp1_model.joblib
out = p.predict(sensor_payload)              # -> machine_id, timestamp, risk_score, anomaly,
                                             #    predicted_fault, severity, model_version
```
Stateful (one buffer per machine): the first 300 s per machine return risk 0 / NONE (warm-up).
`build_prediction_result(out, "FOG_A")` adds `message_id` and `fog_id` for `fog/{fog_id}/predictions`.
Process-level alternative: `python -m src.inference --stdin` (JSON lines in, predictions out).
Pinned versions (the model is a pickle): see `requirements.txt`.

# MP1 - Industrial Simulation and AI-Based Predictive Maintenance

Responsable : Member 1 - Branche : `mp1/simulator`

## Perimetre
- Simuler 12 machines (zones A/B/C) produisant une mesure/seconde au format `contracts/DATA_CONTRACT.md` section 1.
- Modeliser normal, usure de roulement, surchauffe, desequilibre mecanique, surcharge electrique.
- Pretraitement + features (moyennes glissantes, RMS vibration, tendance temperature).
- Detection par seuils (baseline) puis modele Scikit-learn.
- Evaluation : precision, recall, F1, matrice de confusion, taux de fausses alarmes, latence de detection.

## Livrables
- Simulateur executable + jeux d echantillons (`data/samples/`).
- Document des scenarios de defaillance.
- Modele entraine + interface d inference `predict(machine_id, readings) -> risk_score, anomaly, predicted_fault, model_version`.
- Tests pytest, rapport d evaluation avec limites.

## Interface vers les autres
- Publie MQTT `fog/{zone}/sensor/{machine_id}` (MP2 consomme).
- Expose un module importable par MP2 pour la partie ML.
- Peut etre testu hors ligne en ecrivant des JSON sur disque (MP2 relit les fichiers).

## Démarrage
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m src.simulator --machines 12 --duration 60 --out data/samples/
pytest -q
```
