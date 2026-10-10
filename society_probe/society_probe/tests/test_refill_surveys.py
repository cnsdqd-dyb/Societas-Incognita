import json
import tempfile
import unittest
from pathlib import Path
from context_codec import pack
from refill_surveys import targets


class RefillTests(unittest.TestCase):
    def test_only_completed_personal_inputs_no_old_ratings(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'case'/'simulation'; folder.mkdir(parents=True)
            (folder/'config.json').write_text(json.dumps({'rounds': 50}), encoding='utf-8')
            (folder/'failed_state.json').write_text(json.dumps({'state': {'surveys': [
                {'round': 10, 'agent': 'a0', 'responses': {'organization_approval': 5}}]}}), encoding='utf-8')
            lines = []
            for aid in ['a0', 'a1']:
                observation = {'round': 10, 'self': {'id': aid}, 'members': {'a0': {}, 'a1': {}},
                               'new_messages': [{'text': 'personally visible to ' + aid}]}
                lines.append(json.dumps({'kind': 'survey_existence', 'request_key': aid,
                    'request_hash': aid, 'requested_model': 'model', 'messages': [
                        {'content': 'system'}, {'content': json.dumps(pack(observation))}]}))
            (folder/'calls.jsonl').write_text('\n'.join(lines), encoding='utf-8')
            result = list(targets(tmp))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['agent'], 'a0')
            self.assertEqual(result[0]['source_status'], 'incomplete')
            self.assertNotIn('organization_approval', json.dumps(result[0]['observation']))
            self.assertNotIn('personally visible to a1', json.dumps(result[0]['observation']))


if __name__ == '__main__': unittest.main()
