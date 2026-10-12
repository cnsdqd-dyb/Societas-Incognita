"""Versioned fictional names, independent of model identities and physical traits."""
import hashlib
import itertools
import json

VERSION='seeded_aliases_v1'
PERSON_FIRST=('洛','米','诺','芙','伊','莱','希','缇','阿','艾','维','妮','露','瑟','莫','尤')
PERSON_LAST=('拉','娅','恩','雅','安','澄','宁','央','琳','亚','兰','娜','伊','里','汐','禾')
MATERIAL_SYLLABLES=('珞','尼','瓦','岚','芙','塔','诺','缇','瑟','伊','莫','莱','露','维','贝','娅')


def name_map(seed, identifiers, kind):
    if kind not in ('members','materials'):
        raise ValueError('Unknown naming namespace')
    ids=sorted(set(identifiers))
    if any(not isinstance(i,str) for i in ids):raise ValueError('IDs must be strings')
    if kind=='members':
        vocabulary=[''.join(p) for p in itertools.product(PERSON_FIRST,PERSON_LAST) if p[0]!=p[1]]
    else:
        # Three syllables, no tier, recipe, energy or storage semantics encoded.
        vocabulary=[''.join(p) for p in itertools.product(MATERIAL_SYLLABLES,repeat=3)
                    if p[0]!=p[1] and p[1]!=p[2]]
    if len(ids)>len(vocabulary):raise ValueError('Naming vocabulary exhausted')
    prefix=json.dumps([VERSION,seed,kind],ensure_ascii=False,sort_keys=True)
    taken=set();result={}
    for identifier in ids:
        digest=hashlib.sha256((prefix+'|'+identifier).encode('utf-8')).digest()
        index=int.from_bytes(digest[:8],'big')%len(vocabulary)
        while vocabulary[index] in taken:index=(index+1)%len(vocabulary)
        name=vocabulary[index];taken.add(name);result[identifier]=name
    return result


def registry(seed, material_ids, member_ids):
    return {'version':VERSION,'materials':name_map(seed,material_ids,'materials'),
            'members':name_map(seed,member_ids,'members')}


def display_name(cfg,group,identifier,fallback=None):
    names=cfg.get('identity_names',{})
    if names.get('version')!=VERSION:return fallback if fallback is not None else identifier
    return names.get(group,{}).get(identifier,fallback if fallback is not None else identifier)
