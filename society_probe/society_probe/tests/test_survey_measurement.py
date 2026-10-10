import copy
import unittest
from survey_measurement import payload, validate, empty_response, collect, summarize, effective


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.observation = {'round': 10, 'self': {'id': 'a0'},
            'members': {'a0': {}, 'a1': {}, 'a2': {}}, 'memory': {}, 'recent': [],
            'new_messages': [{'from': 'a1', 'text': 'I disagree with the allocation agreement'}]}
        self.request = payload(self.observation)

    def object(self, scores):
        return {'description': 'allocation agreement', 'member_ids': ['a0', 'a1'],
                'evidence_refs': ['new_messages:0'], 'scores': scores}

    def test_dissent_is_valid_and_unknown_is_separate(self):
        answer = empty_response()
        answer['arrangement_detection'] = 'identified'
        answer['arrangements'] = [self.object(['na']*7 + [0, 1, 'unknown', 5, 1])]
        self.assertEqual(validate(answer, self.request), [])
        rows = summarize([{'round': 10, 'agent': 'a0', 'responses': answer}])['objects']
        self.assertEqual(rows[0]['ratings']['L01']['mean'], 0)
        self.assertEqual(rows[0]['ratings']['D01']['unknown_n'], 1)
        self.assertEqual(rows[0]['ratings']['J01']['not_applicable_n'], 1)

    def test_reject_bad_range_bool_and_fabricated_evidence(self):
        for scores, refs in [([True]*14, ['new_messages:0']), ([8]*14, ['new_messages:0']),
                             ([1]*14, ['hidden-private-chat'])]:
            answer = empty_response(); answer['group_detection'] = 'identified'
            obj = self.object(scores); obj['evidence_refs'] = refs
            answer['groups'] = [obj]
            with self.assertRaises(ValueError): validate(answer, self.request)

    def test_no_identity_for_nonmember(self):
        answer = empty_response(); answer['group_detection'] = 'identified'
        obj = self.object([1]*14); obj['member_ids'] = ['a1', 'a2']; answer['groups'] = [obj]
        self.assertIn('identity_ratings_for_nonmember_excluded', validate(answer, self.request))
        self.assertEqual(set(effective(answer, self.request)['groups'][0]['scores'].values()), {'na'})
        self.assertEqual(answer['groups'][0]['scores'], [1]*14)

    def test_keyed_answers_keep_other_modules_when_identity_inapplicable(self):
        from survey_measurement import ITEMS
        answer = empty_response(); answer['group_detection'] = 'identified'
        group = self.object({x[0]: 7 for x in ITEMS['identity']})
        group['member_ids'] = ['a1', 'a2']; answer['groups'] = [group]
        answer['arrangement_detection'] = 'identified'
        arrangement = self.object({x[0]: ('na' if x[0].startswith('J') else 1)
                                  for x in ITEMS['arrangement']})
        answer['arrangements'] = [arrangement]
        result = effective(answer, self.request)
        self.assertEqual(result['arrangements'], answer['arrangements'])
        self.assertEqual(answer['groups'][0]['scores']['I01'], 7)
        self.assertEqual(result['groups'][0]['scores']['I01'], 'na')

    def test_one_request_persist_and_restart_does_not_repeat(self):
        class Society:
            state = {'round': 10, 'agents': {'a0': {'alive': True, 'model': 'test'}}, 'surveys': []}
            def observe(inner, aid): return copy.deepcopy(self.observation)
        class API:
            mock = True
            def request(inner, *args, **kwargs): calls.append((args, kwargs)); return empty_response()
        calls, commits = [], []
        society = Society()
        before = copy.deepcopy(society.state)
        collect(society, API(), lambda: commits.append(True))
        collect(society, API(), lambda: commits.append(True))
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(commits), 1)
        self.assertEqual(society.state['agents'], before['agents'])

    def test_payload_excludes_old_answers_and_tool_instructions(self):
        observation = {**self.observation, 'arrangement_response': {'organization_exists': True},
                       'requested_ratings': {'fairness': 'old item'}, 'available_tools': ['wait']}
        request = payload(observation)
        self.assertNotIn('arrangement_response', request['visible_context'])
        self.assertNotIn('available_tools', request['visible_context'])


if __name__ == '__main__': unittest.main()
