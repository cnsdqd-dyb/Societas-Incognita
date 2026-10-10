import unittest
from context_codec import pack,unpack,serialized


class ContextCodecTests(unittest.TestCase):
    def test_sources_privacy_and_duplicate_messages_survive(self):
        text='只向被邀请且接受的成员开放这条记录，保持它的原始内容。'*8
        messages=[{'round':t,'from':aid,'channel':channel,'text':text}
                  for t,aid,channel in [(1,'a0','public'),(1,'a1','c1'),(2,'a0','public')]]
        payload={'new_messages':messages,'recent':[{'round':1,'observed_messages':messages}],
                 'memory':{'facts':[text]},'stock':0.123456789012345,'unknown':None}
        encoded=pack(payload)
        self.assertEqual(unpack(encoded),payload)
        self.assertLess(len(serialized(encoded)),len(serialized(payload)))

    def test_marker_shaped_user_data_is_literal(self):
        payload={'$text':0,'$table':[['x'],[[1]]],'$object':None,
                 'repeated':['literal reserved text '*100]*8}
        self.assertEqual(unpack(pack(payload)),payload)

    def test_small_payload_keeps_plain_format(self):
        payload={'round':1,'stock':4,'messages':[]}
        self.assertEqual(pack(payload),payload)

    def test_unequal_fields_null_and_missing_survive(self):
        payload={'records':[{'x':None},{'y':1},{}],'text':['重复消息'*100]*6}
        self.assertEqual(unpack(pack(payload)),payload)
