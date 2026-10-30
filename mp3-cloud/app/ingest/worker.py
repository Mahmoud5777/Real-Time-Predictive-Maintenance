"""T5 - Abonnement aux topics publies par MP2.

A faire dans l ordre :
1. construire le client paho avec les settings MQTT ;
2. mapper topic -> kind via `TOPIC_KIND` ;
3. parser avec `app.services.ingest.parse_message` ;
4. inserer avec ON CONFLICT (message_id) DO NOTHING => compteur `duplicates_rejected` (T6) ;
5. exposer les compteurs Prometheus (`ingested_total`, `duplicate_total`, `invalid_total`).
"""

TOPIC_KIND = {
    "fog/+/predictions": "prediction",
    "fog/+/alerts": "alert",
    "fog/+/status": "fog_status",
    "tasks/events": "task_event",
    "fog/+/sensor/+": "sensor",
}


def main() -> None:  # pragma: no cover - point d entree conteneur
    raise NotImplementedError("T5 : implementer la boucle paho-mqtt ici")


if __name__ == "__main__":
    main()
