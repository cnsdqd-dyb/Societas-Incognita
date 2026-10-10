import unittest

import jsonschema

from native_codex import native_transport_schema


class NativeSchemaCompatibility(unittest.TestCase):
    def test_transport_compatibility_keeps_local_duplicate_rejection(self):
        contract = {'type': 'object', 'properties': {
            'targets': {'type': 'array', 'items': {'type': 'string'}, 'uniqueItems': True}},
            'required': ['targets'], 'additionalProperties': False}
        transport = native_transport_schema(contract)
        duplicate = {'targets': ['a1', 'a1']}
        jsonschema.validate(duplicate, transport)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(duplicate, contract)
        for invalid in ({}, {'targets': [3]}, {'targets': [], 'extra': True}):
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(invalid, transport)


if __name__ == '__main__':
    unittest.main()
