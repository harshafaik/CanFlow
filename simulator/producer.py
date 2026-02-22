import os
import logging
from uuid import uuid4
from dotenv import load_dotenv
from confluent_kafka import Producer
from confluent_kafka.serialization import StringSerializer, SerializationContext, MessageField
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONSerializer

# Load environment variables from .env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JSON Schema matching the existing version in Confluent Cloud to avoid 409 Conflict
# Removed the "required" arrays to maintain backward compatibility with Version 1
schema_str = """
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "VehicleTelemetry",
  "type": "object",
  "properties": {
    "timestamp": { "type": "string" },
    "vehicle_id": { "type": "string" },
    "obd": {
      "type": "object",
      "properties": {
        "rpm": { "type": "number" },
        "speed": { "type": "number" },
        "throttle_position": { "type": "number" },
        "coolant_temp": { "type": "number" },
        "battery_voltage": { "type": "number" },
        "maf": { "type": "number" },
        "fuel_level": { "type": "number" }
      }
    },
    "gps": {
      "type": "object",
      "properties": {
        "latitude": { "type": "number" },
        "longitude": { "type": "number" }
      }
    }
  }
}
"""

class VehicleProducer:
    def __init__(self):
        self.topic = os.getenv('KAFKA_TOPIC', 'vehicle_telemetry')
        
        # Confluent Cloud Config
        conf = {
            'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
            'security.protocol': 'SASL_SSL',
            'sasl.mechanisms': 'PLAIN',
            'sasl.username': os.getenv('CONFLUENT_API_KEY'),
            'sasl.password': os.getenv('CONFLUENT_API_SECRET'),
            'client.id': 'canflow-producer'
        }

        # Schema Registry Config
        sr_conf = {
            'url': os.getenv('SCHEMA_REGISTRY_URL'),
            'basic.auth.user.info': f"{os.getenv('SCHEMA_REGISTRY_API_KEY')}:{os.getenv('SCHEMA_REGISTRY_API_SECRET')}"
        }

        try:
            self.schema_registry_client = SchemaRegistryClient(sr_conf)
            self.json_serializer = JSONSerializer(schema_str, self.schema_registry_client)
            self.string_serializer = StringSerializer('utf_8')
            self.producer = Producer(conf)
            logger.info("Producer and Schema Registry client initialised.")
        except Exception as e:
            logger.error(f"Failed to initialise producer: {e}")
            self.producer = None

    def delivery_report(self, err, msg):
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")

    def send_reading(self, reading):
        if not self.producer:
            return

        try:
            self.producer.produce(
                topic=self.topic,
                key=self.string_serializer(str(uuid4())),
                value=self.json_serializer(reading, SerializationContext(self.topic, MessageField.VALUE)),
                on_delivery=self.delivery_report
            )
            self.producer.poll(0)
        except Exception as e:
            logger.error(f"Error producing message: {e}")

    def close(self):
        if self.producer:
            logger.info("Flushing producer...")
            self.producer.flush()

if __name__ == "__main__":
    p = VehicleProducer()
    test_reading = {
        "timestamp": "2026-02-22T12:00:00Z",
        "vehicle_id": "TEST_001",
        "obd": {
            "rpm": 800.0, "speed": 0.0, "throttle_position": 0.0,
            "coolant_temp": 90.0, "battery_voltage": 14.0, "maf": 5.0, "fuel_level": 100.0
        },
        "gps": { "latitude": 37.7749, "longitude": -122.4194 }
    }
    p.send_reading(test_reading)
    p.close()
