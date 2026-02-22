import os
import json
import logging
from kafka import KafkaProducer
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VehicleProducer:
    def __init__(self, bootstrap_servers=None, topic=None):
        self.bootstrap_servers = bootstrap_servers or os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092').split(',')
        self.topic = topic or os.getenv('KAFKA_TOPIC', 'vehicle_telemetry')
        
        # Confluent Cloud / SASL Authentication details
        self.api_key = os.getenv('CONFLUENT_API_KEY')
        self.api_secret = os.getenv('CONFLUENT_API_SECRET')
        
        self.producer = None
        self._connect()

    def _connect(self):
        try:
            # Prepare configuration for Confluent Cloud (SASL_SSL + PLAIN)
            # If API keys are missing, it defaults to a local connection (PLAINTEXT)
            kwargs = {
                "bootstrap_servers": self.bootstrap_servers,
                "value_serializer": lambda v: json.dumps(v).encode('utf-8'),
                "acks": 'all',
                "retries": 5
            }

            if self.api_key and self.api_secret:
                logger.info("Configuring SASL_SSL authentication for Confluent Cloud...")
                kwargs.update({
                    "security_protocol": "SASL_SSL",
                    "sasl_mechanism": "PLAIN",
                    "sasl_plain_username": self.api_key,
                    "sasl_plain_password": self.api_secret,
                })
            else:
                logger.info("No API keys found, connecting via PLAINTEXT...")

            self.producer = KafkaProducer(**kwargs)
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
