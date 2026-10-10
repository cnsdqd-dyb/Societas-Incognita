"""Runtime provenance and empirical float checks, never formal certificates."""
import math
import platform
import sys


def runtime_environment():
    # Avoid hostname, usernames, paths and credentials in public reports.
    return {
        'python_version': platform.python_version(),
        'python_implementation': platform.python_implementation(),
        'operating_system': platform.system(),
        'os_release': platform.release(),
        'machine_architecture': platform.machine(),
        'pointer_bits': 64 if sys.maxsize > 2**32 else 32,
        'float_radix': sys.float_info.radix,
        'float_mantissa_bits': sys.float_info.mant_dig,
        'float_epsilon': sys.float_info.epsilon,
        'float_rounding_mode': sys.float_info.rounds,
    }


class FloatReplayAudit:
    """Measure distance OUTSIDE rational intervals, not exact rational error."""
    def __init__(self, tolerance=1e-7):
        self.tolerance = tolerance
        self.count = 0
        self.max_error = 0.0
        self.max_scaled_error = 0.0
        self.worst_location = None

    def compare(self, lo, hi, value, location):
        if not math.isfinite(value):
            raise ValueError('Nonfinite float state: '+location)
        error = max(float(lo)-value, value-float(hi), 0.0)
        scaled = error/max(1.0, abs(value))
        self.count += 1
        self.max_error = max(self.max_error, error)
        if scaled > self.max_scaled_error:
            self.max_scaled_error, self.worst_location = scaled, location
        if scaled > self.tolerance:
            raise ValueError('Float trajectory diverges from certified interval model: '+location)

    def report(self):
        return {
            'status': 'empirical_float_replay_only',
            'runtime': runtime_environment(),
            'comparisons': self.count,
            'distance_definition': 'max(float(lo)-value, value-float(hi), 0)',
            'endpoint_conversion': 'rational endpoints converted to Python float; not a directed-rounding guarantee',
            'acceptance_rule': 'distance <= tolerance * max(1, abs(value))',
            'tolerance': self.tolerance,
            'max_interval_violation': self.max_error,
            'max_scaled_interval_violation': self.max_scaled_error,
            'worst_scaled_violation_location': self.worst_location,
            'formal_ieee_equivalence': False,
        }
