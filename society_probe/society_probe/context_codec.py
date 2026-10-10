"""Reversible prompt encoding. No dropping, merging, rounding or summarizing evidence."""
import json
from collections import Counter


MARKERS={'$text','$table','$object'}


def serialized(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':'))


def pack(payload):
    counts=Counter()
    def count(value):
        if isinstance(value,str):counts[value]+=1
        elif isinstance(value,list):
            for child in value:count(child)
        elif isinstance(value,dict):
            for child in value.values():count(child)
    count(payload)
    texts=[s for s,n in counts.items() if len(s)>=60 and n>=2]
    indices={s:i for i,s in enumerate(texts)}
    def encode(value):
        if isinstance(value,str) and value in indices:return {'$text':indices[value]}
        if isinstance(value,dict):
            if MARKERS.intersection(value):return {'$object':[[k,encode(v)] for k,v in value.items()]}
            return {k:encode(v) for k,v in value.items()}
        if isinstance(value,list):
            plain=[encode(v) for v in value]
            if len(value)>=2 and all(isinstance(v,dict) for v in value):
                columns=list(value[0])
                if columns and all(set(v)==set(columns) for v in value):
                    table={'$table':[columns,[[encode(v[k]) for k in columns] for v in value]]}
                    if len(serialized(table))<len(serialized(plain)):return table
            return plain
        return value
    packed={'encoding':'compact_v1: $text indexes text_pool (0-based); $table=[columns,rows] '
            'represents a list of objects; $object is literal key/value pairs. '
            'All original observations, message sources and visibility are preserved.',
            'text_pool':texts,'payload':encode(payload)}
    # Small inputs should not pay for a codec they do not need.
    collision=(isinstance(payload,dict) and set(payload)=={'encoding','text_pool','payload'}
               and str(payload['encoding']).startswith('compact_v1:'))
    return packed if collision or len(serialized(packed))<len(serialized(payload)) else payload


def unpack(packed):
    if not isinstance(packed,dict) or not str(packed.get('encoding','')).startswith('compact_v1:'):
        return packed
    texts=packed['text_pool']
    def decode(value):
        if isinstance(value,list):return [decode(v) for v in value]
        if isinstance(value,dict):
            if set(value)=={'$text'}:return texts[value['$text']]
            if set(value)=={'$table'}:
                columns,rows=value['$table']
                return [{k:decode(v) for k,v in zip(columns,row)} for row in rows]
            if set(value)=={'$object'}:return {k:decode(v) for k,v in value['$object']}
            return {k:decode(v) for k,v in value.items()}
        return value
    return decode(packed['payload'])
