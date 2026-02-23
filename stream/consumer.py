import os
import sys
import logging
from dotenv import load_dotenv
from confluent_kafka import Consumer, KafkaError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONDeserializer
from confluent_kafka.serialization import SerializationContext, MessageField

# Ensure we can import from simulator/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'simulator')))
from producer import schema_str

from transforms import transform_telemetry
from writer import ClickHouseWriter

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def dict_to_telemetry(obj, ctx):
    """Pass-through for JSONDeserializer's from_dict hook."""
    return obj

class TelemetryConsumer:
    def __init__(self):
        self.topic = os.getenv('KAFKA_TOPIC', 'vehicle.telemetry.raw')
        
        # Confluent Cloud Config
        conf = {
            'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
            'security.protocol': 'SASL_SSL',
            'sasl.mechanisms': 'PLAIN',
            'sasl.username': os.getenv('CONFLUENT_API_KEY'),
            'sasl.password': os.getenv('CONFLUENT_API_SECRET'),
            'group.id': 'canflow-stream-consumer',
            'auto.offset.reset': 'latest'
        }

        # Schema Registry Config
        sr_conf = {
            'url': os.getenv('SCHEMA_REGISTRY_URL'),
            'basic.auth.user.info': f"{os.getenv('SCHEMA_REGISTRY_API_KEY')}:{os.getenv('SCHEMA_REGISTRY_API_SECRET')}"
        }

        try:
            self.schema_registry_client = SchemaRegistryClient(sr_conf)
            # Use explicit keyword arguments to satisfy the library's strict signature checks
            self.json_deserializer = JSONDeserializer(
                schema_str=schema_str,
                from_dict=dict_to_telemetry,
                schema_registry_client=self.schema_registry_client
            )
            self.consumer = Consumer(conf)
            self.writer = ClickHouseWriter()
            logger.info(f"Consumer initialised. Subscribed to {self.topic}")
        except Exception as e:
            logger.error(f"Failed to initialise consumer components: {e}")
            raise

    def run(self):
        try:
            self.consumer.subscribe([self.topic])
            
            while True:
                msg = self.consumer.poll(1.0)

                if msg is None:
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                        continue

                # 1. Deserialise
                try:
                    raw_payload = self.json_deserializer(
                        msg.value(), 
                        SerializationContext(msg.topic(), MessageField.VALUE)
                    )
                    logger.debug(f"Received message from Kafka: {raw_payload.get('vehicle_id')}")
                except Exception as e:
                    logger.error(f"Deserialisation failure: {e}")
                    continue

                # 2. Transform
                try:
                    processed_data = transform_telemetry(raw_payload)
                except Exception as e:
                    logger.error(f"Transformation failure for vehicle {raw_payload.get('vehicle_id')}: {e}")
                    continue

                # 3. Write
                try:
                    self.writer.add(processed_data)
                except Exception as e:
                    logger.error(f"Writer failure: {e}")
                    continue

        except KeyboardInterrupt:
            logger.info("Shutdown signal received.")
        finally:
            self.close()

    def close(self):
        logger.info("Closing consumer and flushing writer...")
        if self.consumer:
            self.consumer.close()
        if self.writer:
            self.writer.close()
        logger.info("Graceful exit complete.")

if __name__ == "__main__":
    consumer = TelemetryConsumer()
    consumer.run()
