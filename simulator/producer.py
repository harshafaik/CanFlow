import json
import logging
from kafka import KafkaProducer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VehicleProducer:
    def __init__(self, bootstrap_servers=['localhost:9092'], topic='vehicle_telemetry'):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer = None
        self._connect()

    def _connect(self):
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=5
            )
            logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            self.producer = None

    def send_reading(self, reading):
        if not self.producer:
            logger.warning("Producer not connected. Reading will be dropped.")
            return

        try:
            future = self.producer.send(self.topic, value=reading)
            # Block for a short time to ensure delivery
            future.get(timeout=10)
            logger.debug(f"Sent reading for vehicle {reading.get('vehicle_id')}")
        except Exception as e:
            logger.error(f"Error sending reading to Kafka: {e}")

    def close(self):
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("Kafka producer closed.")

if __name__ == "__main__":
    # Quick test if run directly
    test_producer = VehicleProducer()
    test_reading = {"vehicle_id": "TEST_001", "status": "active"}
    test_producer.send_reading(test_reading)
    test_producer.close()
