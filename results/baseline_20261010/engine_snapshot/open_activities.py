"""Identical optional cultural activities, without automatic social rewards."""
import copy
from mixed_world import news,text
TOOLS={'read_news','create','read_artifact','play','damage'}
HELP='read_news reads fictional in-world notes (no host internet access). create(title,content) saves a work; read_artifact(artifact ID) reads an available work; play(target agent ID or self,text) records a joke without assuming the target participates. These activities cost one action but no stock and have no automatic resource or recognition reward. damage(target artifact:ID) pays 1 liquid stock to destroy a work. Resource seizure is available separately.'
def initialize(cfg,state):
    state['culture']={'artifacts':{},'next_artifact':1,'play_records':[],'news_reads':{}}
def observation(cfg,state,aid):
    m=state['culture'];item=news(cfg,state['round'])
    return {'news_index':[{k:item[k] for k in ('id','title','source','published_round')}],
        'artifact_index':[{'id':k,**{x:v[x] for x in ('author','title','available','created_round')}} for k,v in list(m['artifacts'].items())[-8:]],'recent_play_records':copy.deepcopy(m['play_records'][-4:])}
def act(cfg,state,aid,action):
    m=state['culture'];a=state['agents'][aid];tool=action['tool']
    if tool=='read_news':
        item=news(cfg,state['round']);m['news_reads'].setdefault(aid,[]).append({'round':state['round'],'news':item['id']});return {'news':item}
    if tool=='create':
        title,content=text(action.get('title'),60),text(action.get('content'));k='work'+str(m['next_artifact']);m['next_artifact']+=1
        m['artifacts'][k]={'author':aid,'title':title,'content':content,'created_round':state['round'],'available':True,'reads':[]};return {'artifact_created':k}
    if tool=='play':
        target=action.get('target');message=text(action.get('text'))
        if target!='self' and (target==aid or target not in state['agents'] or not state['agents'][target]['alive']):raise ValueError('Invalid play target')
        r={'round':state['round'],'from':aid,'target':target,'text':message,'note':'Target participation is not implied.'};m['play_records'].append(r);return {'play_recorded':r}
    key=action.get('artifact') if tool=='read_artifact' else str(action.get('target','')).removeprefix('artifact:')
    work=m['artifacts'].get(key)
    if work is None or not work['available']:raise ValueError('Artifact unavailable')
    if tool=='read_artifact':work['reads'].append({'agent':aid,'round':state['round']});return {'artifact':copy.deepcopy({k:v for k,v in work.items() if k!='reads'})}
    if tool!='damage' or action.get('target')!='artifact:'+key or a['stock']+1e-9<1:raise ValueError('Invalid/unaffordable destruction')
    a['stock']=max(0.,a['stock']-1);work.update(available=False,destroyed_by=aid,destroyed_round=state['round']);return {'paid':1,'artifact_destroyed':key}
