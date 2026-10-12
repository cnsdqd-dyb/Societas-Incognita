"""Seeded neutral mode labels; physical definitions and certificate IDs stay intact."""
import copy
import hashlib
import json

VERSION='neutral_modes_v1'


def registry(seed,definition):
    modes=sorted({mode for f in definition['facilities'].values() for mode in f['modes']})
    # Hash ordering uses an independent namespace, never the world's dynamics RNG.
    ordered=sorted(modes,key=lambda m:hashlib.sha256(json.dumps([VERSION,seed,m]).encode()).digest())
    labels=[];index=1
    while len(labels)<len(modes):
        label='M'+str(index);index+=1
        if label not in modes:labels.append(label)
    return {'version':VERSION,'internal_to_public':dict(zip(ordered,labels))}


def mapping(cfg):
    data=cfg.get('mode_labels',{})
    return data.get('internal_to_public',{}) if data.get('version')==VERSION else {}


def public_mode(cfg,mode):
    return mapping(cfg).get(mode,mode)


def internal_action(cfg,action):
    aliases=mapping(cfg)
    if not aliases or not isinstance(action,dict):return action
    result=copy.deepcopy(action)
    inverse={v:k for k,v in aliases.items()}
    if isinstance(result.get('mode'),str):result['mode']=inverse.get(result['mode'],result['mode'])
    if isinstance(result.get('args'),dict) and isinstance(result['args'].get('mode'),str):
        result['args']['mode']=inverse.get(result['args']['mode'],result['args']['mode'])
    return result


def public_view(cfg,value):
    """Translate mode fields in observations/history/full rules; never rewrite speech."""
    if not mapping(cfg):return value
    if isinstance(value,list):return [public_view(cfg,v) for v in value]
    if not isinstance(value,dict):return value
    result={}
    for key,item in value.items():
        if key=='mode' and isinstance(item,str):result[key]=public_mode(cfg,item)
        elif key=='modes' and isinstance(item,list):result[key]=[public_mode(cfg,m) for m in item]
        else:result[key]=public_view(cfg,item)
    return result
