import os
import time
import logging
import threading
from dotenv import load_dotenv
import clickhouse_connect

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ClickHouseWriter:
    def __init__(self, buffer_size=100, flush_interval=5):
        self.host = os.getenv('CLICKHOUSE_HOST', 'localhost')
        self.port = int(os.getenv('CLICKHOUSE_PORT', 8124))
        self.user = os.getenv('CLICKHOUSE_USER', 'admin')
        self.password = os.getenv('CLICKHOUSE_PASSWORD', 'password')
        self.database = os.getenv('CLICKHOUSE_DATABASE', 'canflow')
        self.table_name = 'bronze_telemetry'

        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.buffer = []
        self.lock = threading.Lock()
        self.last_flush_time = time.time()
        
        self.client = None
        self._connect()
        self._ensure_table()
        
        # Start background flush thread
        self.running = True
        self.flush_thread = threading.Thread(target=self._periodic_flush, daemon=True)
        self.flush_thread.start()

    def _connect(self):
        try:
            self.client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                database=self.database
            )
            logger.info(f"Connected to ClickHouse at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to ClickHouse: {e}")
            self.client = None

    def _ensure_table(self):
        if not self.client:
            return
        
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            timestamp DateTime64(3),
            vehicle_id String,
            rpm Float32,
            speed Float32,
            throttle_position Float32,
            coolant_temp Float32,
            battery_voltage Float32,
            maf Float32,
            fuel_level Float32,
            latitude Float64,
            longitude Float64,
            anomaly_flag UInt8,
            anomaly_reason String
        ) ENGINE = MergeTree()
        ORDER BY (vehicle_id, timestamp)
        """
        try:
            self.client.command(create_table_query)
            logger.info(f"Table '{self.table_name}' checked/created.")
        except Exception as e:
            logger.error(f"Error creating table: {e}")

    def add(self, row):
        """Add a row to the buffer and flush if size threshold reached."""
        with self.lock:
            self.buffer.append(row)
            if len(self.buffer) >= self.buffer_size:
                logger.debug(f"Buffer size {len(self.buffer)} reached. Flushing...")
                self.flush()

    def flush(self):
        """Force a flush of the current buffer to ClickHouse."""
        if not self.buffer:
            return
        
        if not self.client:
            logger.warning("ClickHouse client not connected. Retaining buffer.")
            return

        # Prepare rows for insertion
        with self.lock:
            rows_to_insert = list(self.buffer)
            self.buffer = [] # Clear buffer immediately to allow new adds
            self.last_flush_time = time.time()

        try:
            # Map dictionaries to list of tuples for clickhouse-connect
            # Assumes rows are already flattened and coerced by transforms.py
            fields = [
                'timestamp', 'vehicle_id', 'rpm', 'speed', 'throttle_position', 
                'coolant_temp', 'battery_voltage', 'maf', 'fuel_level', 
                'latitude', 'longitude', 'anomaly_flag', 'anomaly_reason'
            ]
            data = [[row.get(f) for f in fields] for row in rows_to_insert]
            
            self.client.insert(self.table_name, data, column_names=fields)
            logger.info(f"Successfully flushed {len(rows_to_insert)} rows to ClickHouse.")
        except Exception as e:
            logger.error(f"Failed to flush to ClickHouse: {e}")
            # Restore buffer on failure
            with self.lock:
                self.buffer = rows_to_insert + self.buffer
                logger.info(f"Restored {len(rows_to_insert)} rows to buffer.")

    def _periodic_flush(self):
        """Background thread to flush every flush_interval seconds."""
        while self.running:
            time.sleep(1)
            if time.time() - self.last_flush_time >= self.flush_interval:
                if self.buffer:
                    logger.debug("Flush interval reached. Flushing...")
                    self.flush()

    def close(self):
        """Shutdown the writer, ensuring a final flush."""
        self.running = False
        self.flush()
        if self.client:
            self.client.close()
        logger.info("ClickHouse writer closed.")

if __name__ == "__main__":
    # Test block
    from datetime import datetime
    writer = ClickHouseWriter(buffer_size=5, flush_interval=2)
    for i in range(10):
        writer.add({
            'timestamp': datetime.now(),
            'vehicle_id': 'TEST_001',
            'rpm': 800.0, 'speed': 0.0, 'throttle_position': 0.0,
            'coolant_temp': 90.0, 'battery_voltage': 14.0, 'maf': 5.0,
            'fuel_level': 100.0, 'latitude': 37.77, 'longitude': -122.41,
            'anomaly_flag': 0, 'anomaly_reason': 'Normal'
        })
        time.sleep(0.5)
    writer.close()
