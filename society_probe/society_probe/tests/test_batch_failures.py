import tempfile
import unittest
from pathlib import Path
from run_batch import service_failure


class ServiceFailureTests(unittest.TestCase):
    def classify(self, text):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'process.log'
            path.write_text(text,encoding='utf-8')
            return service_failure(path)

    def test_account_failure_stops_without_retry(self):
        for code in (401,402,403):
            self.assertEqual(self.classify(f'RuntimeError: OpenRouter HTTP {code}; no substitution.'),f'account_http_{code}')

    def test_latest_failure_wins_over_previous_attempt(self):
        self.assertIsNone(self.classify('RuntimeError: OpenRouter HTTP 402\nValueError: Non-JSON response'))

    def test_transport_and_provider_failures_are_transient(self):
        for message in ('TimeoutError: read timed out','RuntimeError: OpenRouter HTTP 429','RuntimeError: OpenRouter HTTP 503'):
            self.assertEqual(self.classify(message),'transient_service')

    def test_format_failure_is_not_account_failure(self):
        self.assertIsNone(self.classify('ValueError: Non-JSON response'))
