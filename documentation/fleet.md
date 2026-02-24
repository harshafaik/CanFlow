# Fleet Configuration

CanFlow simulates a diverse fleet of 25+ unique Indian Internal Combustion Engine (ICE) vehicle models, each with multiple instances and unique wear characteristics.

## Fleet Structure

The fleet is generated based on the list of models in `config/fleet_config.yaml`. For every model, multiple persistent instances are created.

- **Instances per Model**: Configured via `INSTANCES_PER_MODEL` in `.env`.
- **Naming Convention**: `MODEL_INITIALS-INDEX` (e.g., `MSS-001` for Maruti Suzuki Swift instance 1, `TA-005` for Tata Ace instance 5).

## Vehicle Categories

### 1. Passenger Vehicles
- **Major Brands**: Maruti Suzuki, Tata Motors, Hyundai, Mahindra, Toyota, Kia.
- **Characteristics**: Higher idle RPM (850), higher top speed (180 km/h), and standard 12V electrical systems (14.2V baseline).

### 2. Commercial Vehicles
- **Major Brands**: Tata Motors, Mahindra, Ashok Leyland, Force, Eicher.
- **Characteristics**: Lower idle RPM (650), restricted top speed (100 km/h), and heavy-duty 24V electrical systems (26.5V baseline).

## Sensor Profiles & Realism

| Metric | Passenger | Commercial |
| :--- | :--- | :--- |
| **Idle RPM** | 850 | 650 |
| **Max RPM** | 6500 | 4000 |
| **Max Speed** | 180 km/h | 100 km/h |
| **Coolant Temp** | 90°C | 92°C |
| **System Voltage** | 14.2V | 26.5V |

### Wear Factor
Every specific vehicle instance is assigned a unique **Wear Factor** (between 0.95 and 1.15) upon initialization. This factor permanently offsets the vehicle's sensor baselines (RPM, Temperature, MAF) to simulate:
- **Vehicle Age**: Older vehicles might run slightly hotter or have higher idle vibrations.
- **Manufacturing Variance**: No two vehicles perform identically in the real world.

## Physical Constraints

The simulation enforces strict physical bounds at the sensor level (`simulator/sensors.py`) to ensure data quality:
- **Speed/RPM**: Hard-clamped at 0 (no negative values).
- **Throttle**: Clamped between 0-100%.
- **Battery**: Hard floor at 10.5V.
