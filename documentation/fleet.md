# Fleet Configuration

CanFlow simulates a diverse fleet of Indian Internal Combustion Engine (ICE) vehicles, categorized by their operational profiles.

## Vehicle Categories

The fleet is divided into two primary categories, each with distinct sensor baselines and physical constraints:

### 1. Passenger Vehicles
- **Models**: Maruti Suzuki Swift, Hyundai i20, Tata Nexon, Honda City.
- **Characteristics**: Higher idle RPM (850), higher top speed (180 km/h), and more aggressive acceleration.
- **Electrical**: Standard 12V systems (14.2V baseline).

### 2. Commercial Vehicles
- **Models**: Tata Ace, Mahindra Bolero, Ashok Leyland Dost, Force Traveller.
- **Characteristics**: Lower idle RPM (650), restricted top speed (100 km/h), and slower acceleration under load.
- **Electrical**: Often 24V systems (26.5V baseline).

## Sensor Profiles

Baselines and physical limits are externalized in `config/fleet_config.yaml`. This allows for easy adjustment of fleet characteristics without modifying core simulation logic.

| Metric | Passenger | Commercial |
| :--- | :--- | :--- |
| **Idle RPM** | 850 | 650 |
| **Max RPM** | 6500 | 4000 |
| **Max Speed** | 180 km/h | 100 km/h |
| **Coolant Temp** | 90°C | 92°C |
| **System Voltage** | 14.2V | 26.5V |

## Physical Constraints

The simulation enforces strict physical bounds at the sensor level (`simulator/sensors.py`) to ensure data quality:
- **Speed/RPM**: Hard-clamped at 0 (no negative values).
- **Throttle**: Clamped between 0-100%.
- **Battery**: Hard floor at 10.5V to simulate a "dead" battery rather than impossible negative voltages.
