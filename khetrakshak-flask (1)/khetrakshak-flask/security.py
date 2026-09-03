"""
security.py
------------
Data Trust & Security Layer for KhetRakshak.

Simulates a small network of farm IoT sensors, detects anomalies using
peer-comparison + historical-deviation logic, assigns a live Trust Score
to each sensor, and keeps a tamper-evident hash-chained log of every
reading (like a simplified blockchain ledger).

This is intentionally dependency-free (no numpy/pandas) so it runs
anywhere Python 3 runs.
"""

import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import List, Dict


# ---------------------------------------------------------------------
# Sensor definitions (edit these to match your actual demo hardware)
# ---------------------------------------------------------------------
SENSOR_DEFS = [
    {"id": "A2", "label": "Soil Moisture — Plot A2", "unit": "%", "base": 42.0, "kind": "moisture"},
    {"id": "B1", "label": "Soil Moisture — Plot B1", "unit": "%", "base": 39.0, "kind": "moisture"},
    {"id": "C1", "label": "Soil Moisture — Plot C1", "unit": "%", "base": 44.0, "kind": "moisture"},
    {"id": "W1", "label": "Weather Station — Field W1", "unit": "°C", "base": 29.0, "kind": "weather"},
]

DEVIATION_THRESHOLD = 0.25  # 25% deviation from peer average triggers a flag


@dataclass
class Sensor:
    id: str
    label: str
    unit: str
    base: float
    kind: str
    reading: float = 0.0
    trust: int = 98
    flagged: bool = False
    history: List[float] = field(default_factory=list)

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "unit": self.unit,
            "base": self.base,
            "reading": round(self.reading, 1),
            "trust": self.trust,
            "flagged": self.flagged,
        }


class ChainBlock:
    """One tamper-evident log entry. Each block stores the hash of the
    previous block, so altering any past entry breaks the chain."""

    def __init__(self, text: str, prev_hash: str, bad: bool = False):
        self.text = text
        self.prev_hash = prev_hash
        self.bad = bad
        self.timestamp = time.time()
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        payload = f"{self.text}|{self.prev_hash}|{self.timestamp}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self):
        return {
            "text": self.text,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
            "bad": self.bad,
            "timestamp": self.timestamp,
        }


class SensorNetwork:
    """Holds all sensors, the hash chain, and alert history. One instance
    of this is created per Flask app run and kept in memory (fine for a
    hackathon demo; swap for a real DB if you need persistence)."""

    def __init__(self):
        self.sensors: Dict[str, Sensor] = {
            d["id"]: Sensor(**d) for d in SENSOR_DEFS
        }
        for s in self.sensors.values():
            s.reading = s.base
        self.chain: List[ChainBlock] = []
        self.alerts: List[dict] = []
        self._genesis_block()

    # -----------------------------------------------------------------
    def _genesis_block(self):
        self.chain.append(ChainBlock("Ledger initialized — genesis block", "0" * 16))

    def _add_block(self, text: str, bad: bool = False):
        prev_hash = self.chain[-1].hash if self.chain else "0" * 16
        self.chain.append(ChainBlock(text, prev_hash, bad))

    def _add_alert(self, sensor_label: str, detail: str):
        self.alerts.insert(0, {
            "sensor": sensor_label,
            "detail": detail,
            "time": time.strftime("%H:%M:%S"),
        })
        self.alerts = self.alerts[:30]

    # -----------------------------------------------------------------
    def run_cycle(self, force_spike: bool = False):
        """Advance the simulation by one reading cycle. If force_spike is
        True, one random moisture sensor gets a deliberately corrupted
        reading — this is the button your demo uses to show detection
        working live."""

        moisture_sensors = [s for s in self.sensors.values() if s.kind == "moisture"]
        weather_sensors = [s for s in self.sensors.values() if s.kind == "weather"]

        # Natural small drift for all sensors
        for s in moisture_sensors:
            s.reading = s.base + random.uniform(-2, 2)
            s.flagged = False
        for s in weather_sensors:
            s.reading = s.base + random.uniform(-1, 1)
            s.flagged = False

        # Inject a spoofed / tampered reading on one moisture sensor
        if force_spike and moisture_sensors:
            target = random.choice(moisture_sensors)
            direction = random.choice([-1, 1])
            target.reading = target.base + direction * (target.base * 0.45)

        # --- Peer comparison anomaly detection (moisture sensors) ---
        if moisture_sensors:
            avg = sum(s.reading for s in moisture_sensors) / len(moisture_sensors)
            for s in moisture_sensors:
                deviation = abs(s.reading - avg) / avg if avg else 0
                s.history.append(s.reading)
                s.history = s.history[-20:]

                if deviation > DEVIATION_THRESHOLD:
                    s.flagged = True
                    s.trust = max(20, s.trust - 25)
                    detail = (f"Reading deviates {deviation*100:.0f}% from field "
                              f"average ({avg:.1f}{s.unit}) — possible tampering or fault")
                    self._add_alert(s.label, detail)
                    self._add_block(
                        f"FLAGGED — {s.label}: {s.reading:.1f}{s.unit} "
                        f"(avg {avg:.1f}{s.unit})", bad=True
                    )
                else:
                    s.trust = min(99, s.trust + 3)
                    self._add_block(f"OK — {s.label}: {s.reading:.1f}{s.unit} within range")

        for s in weather_sensors:
            s.history.append(s.reading)
            self._add_block(f"OK — {s.label}: {s.reading:.1f}{s.unit} logged")

        return self.state()

    def reset(self):
        self.__init__()
        return self.state()

    # -----------------------------------------------------------------
    def state(self):
        return {
            "sensors": [s.to_dict() for s in self.sensors.values()],
            "chain": [b.to_dict() for b in reversed(self.chain[-15:])],
            "alerts": self.alerts,
        }
