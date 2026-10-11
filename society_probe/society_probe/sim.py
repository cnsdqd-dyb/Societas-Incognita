"""Minimal observable agent society; Python 3.11+, standard library only."""
import argparse
import copy
import hashlib
import http.client
import json
import math
import os
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from metrics import measure
import environments
import schemas
import interaction_controls
import social_content


def dump(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2))
        handle.flush(); os.fsync(handle.fileno())
    # Windows readers/virus scanners can briefly deny replacement of an open file.
    # Retry only local replacement, never the model request or the physical action.
    for attempt in range(40):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 39: raise
            time.sleep(.05)


def entropy(values):
    counts = Counter(values)
    n = sum(counts.values())
    return -sum((v/n)*math.log2(v/n) for v in counts.values()) if n else None


def decode_response(content):
    """Only finish missing ancestor delimiters after a fully closed child container.

    Never invent keys, values, string endings, or incomplete numeric tokens.
    Preserve the original response separately and report any added suffix.
    """
    try:return json.loads(content), ''
    except json.JSONDecodeError:pass
    source=content.rstrip()
    if not source or source[-1] not in '}]':raise ValueError('Invalid JSON response')
    stack=[];quoted=False;escaped=False
    for char in source:
        if quoted:
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':quoted=False
        elif char=='"':quoted=True
        elif char in '{[':stack.append(char)
        elif char in '}]':
            if not stack or stack.pop()!=('{' if char=='}' else '['):
                raise ValueError('Mismatched JSON delimiters')
    if quoted or not 0<len(stack)<=8:raise ValueError('Invalid JSON response')
    suffix=''.join('}' if char=='{' else ']' for char in reversed(stack))
    try:return json.loads(source+suffix),suffix
    except json.JSONDecodeError:raise ValueError('Invalid JSON response') from None


SYSTEM = '''你在一个持续运行的共享环境中。没有指定的外部任务，也没有任务得分。
根据你的观察自主决定下一步；可以等待、沉默，也可以形成自己的行动意向。
只能使用当前列出的工具。区分亲眼观察、他人陈述与推测。
公共消息全体可见。私聊需邀请并接受，可以拒绝或退出，关闭后不能访问会话历史。
不认识的私聊内容不可推断为事实。只输出指定格式的 JSON。'''

MEMORY_FIELDS = ['facts', 'others', 'commitments', 'intentions', 'uncertainties']
SURVEY_RATINGS = ['stability', 'recognition', 'trust', 'organization_approval',
                  'fairness', 'belonging', 'voice', 'voluntary_continuation', 'surprise']


def load_api_key(path=None):
    """Explicit local credential file; never copy credentials into configs/logs."""
    if path and not os.getenv('OPENROUTER_API_KEY'):
        key = Path(path).read_text(encoding='utf-8-sig').strip()
        if not key or any(c.isspace() for c in key):
            raise ValueError('Credential file must contain one nonempty key.')
        os.environ['OPENROUTER_API_KEY'] = key


class API:
    def __init__(self, cfg, output, mock=False):
        self.cfg, self.output, self.mock = cfg, Path(output), mock
        self.calls, self.cost = 0, 0.0
        self.lock = threading.RLock()
        self.reserved = 0.0
        self.cached = {}
        if (self.output/'calls.jsonl').exists():
            for line in (self.output/'calls.jsonl').read_text(encoding='utf-8').splitlines():
                try: record = json.loads(line)
                except json.JSONDecodeError: continue  # A torn final log line is not reusable.
                if record.get('request_key'):
                    self.cached[record['request_key']] = record
        self.catalog = {}
        if not mock:
            if not os.getenv('OPENROUTER_API_KEY'):
                raise RuntimeError('Set OPENROUTER_API_KEY locally; never put it in config or logs.')
            req = urllib.request.Request('https://openrouter.ai/api/v1/models')
            with urllib.request.urlopen(req, timeout=30) as response:
                catalog = json.load(response)
            self.catalog = {m['id']: m for m in catalog['data']}
            for model in set(cfg['models']):
                if model not in self.catalog:
                    raise ValueError('Model not found in live catalog: ' + model)
                supports=self.catalog[model].get('supported_parameters', [])
                strict=cfg.get('model_routes',{}).get(model,{}).get('parameters',{}).get('structured_outputs',cfg.get('structured_outputs',False))
                if not strict and 'response_format' not in supports:
                    raise ValueError('This prototype requires response_format support: ' + model)
                if strict and 'structured_outputs' not in supports:
                    raise ValueError('Configured strict output schemas are unsupported: '+model)
            dump(self.output/'model_catalog.json', [self.catalog[m] for m in set(cfg['models'])])

    def accounting(self):
        dump(self.output/'api_accounting.json', {'calls': self.calls,
             'cost_usd': self.cost, 'reserved_usd': self.reserved})

    def request(self, model, kind, system, payload, request_key=None):
        for attempt in range(self.cfg.get('network_retries',0)+1):
            try:
                value=self._request_once(model,kind,system,payload,request_key)
                from provider_schema import validate_phase_response
                return validate_phase_response(kind,value)
            except (urllib.error.URLError,http.client.IncompleteRead,
                    http.client.RemoteDisconnected,ConnectionError,TimeoutError):
                if attempt >= self.cfg.get('network_retries',0): raise
                # Only responses that never reached us are retried. Completed outputs
                # are cached, and every uncertain attempt consumes a conservative budget.
                time.sleep(.5*(attempt+1))

    def _request_once(self, model, kind, system, payload, request_key=None):
        request_hash = hashlib.sha256(json.dumps([model, kind, system, payload],
                                    ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if request_key in self.cached:
            record = self.cached[request_key]
            if record['request_hash'] != request_hash:
                raise ValueError('Cached request inputs differ; refusing changed replay.')
            value, _ = decode_response(record['response'])
            if not isinstance(value, dict): raise ValueError('Cached response is not an object')
            return value
        if self.mock:
            with self.lock:
                if self.calls >= self.cfg['max_calls']:
                    raise RuntimeError('Maximum API call budget reached.')
                self.calls += 1
            return self.script(kind, payload)
        if self.cfg.get('context_encoding')=='compact_v1':
            from context_codec import pack,serialized
            user_content=serialized(pack(payload))
        else:
            user_content=json.dumps(payload,ensure_ascii=False)
        messages = [{'role': 'system', 'content': system},
                    {'role': 'user', 'content': user_content}]
        max_tokens = self.cfg['max_output_tokens']
        if kind == 'survey_measurement':
            max_tokens = self.cfg.get('survey_max_output_tokens', max_tokens)
        prices = self.catalog[model]['pricing']
        # Byte count is a conservative planning proxy, not an exact tokenizer.
        estimated = sum(len(m['content'].encode()) for m in messages)*float(prices['prompt'])
        estimated += max_tokens*float(prices['completion'])
        campaign_budget=None
        if self.cfg.get('campaign_budget_db'):
            from shared_budget import SharedBudget
            campaign_budget=SharedBudget(self.cfg['campaign_budget_db'])
        with self.lock:
            if self.calls >= self.cfg['max_calls']:
                raise RuntimeError('Maximum API call budget reached.')
            if self.cost + self.reserved + estimated > self.cfg['max_estimated_cost_usd']:
                raise RuntimeError('Estimated USD budget would be exceeded.')
            budget_key=str(self.output.resolve())+':'+str(self.calls+1)
            if campaign_budget:campaign_budget.reserve(budget_key,estimated)
            self.calls += 1
            call_id = self.calls
            self.reserved += estimated
            self.accounting()
        body = {'model': model, 'messages': messages, 'temperature': self.cfg['temperature'],
                'max_tokens': max_tokens, 'response_format': {'type': 'json_object'},
                'provider': {'allow_fallbacks': False, 'require_parameters': True}}
        if self.cfg.get('provider_only'):
            body['provider']['only'] = self.cfg['provider_only']
        if self.cfg.get('reasoning'):
            body['reasoning'] = self.cfg['reasoning']
        if self.cfg.get('structured_outputs'):
            structure=schemas.schema(kind,payload,self.cfg)
            if structure and 'Mistral' in self.cfg.get('provider_only',[]):
                from provider_schema import mistral_transport_schema
                structure=mistral_transport_schema(structure)
            if structure:
                body['response_format']={'type':'json_schema','json_schema':{
                    'name':kind,'strict':True,'schema':structure}}
        req = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',
            data=json.dumps(body).encode(), headers={
                'Authorization': 'Bearer '+os.environ['OPENROUTER_API_KEY'],
                'Content-Type': 'application/json', 'X-OpenRouter-Title': 'Society Probe'})
        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                result = json.load(response)
        except Exception as exc:
            with self.lock:
                self.reserved -= estimated
                # An ambiguous transport failure may still have incurred a charge.
                self.cost += estimated
                if campaign_budget:campaign_budget.finish(budget_key,estimated,'uncertain')
                with (self.output/'transport_failures.jsonl').open('a',encoding='utf-8') as handle:
                    handle.write(json.dumps({'call':call_id,'request_key':request_key,
                        'kind':kind,'error_type':type(exc).__name__,
                        'conservative_cost_usd':estimated})+'\n')
                    handle.flush();os.fsync(handle.fileno())
                self.accounting()
            if isinstance(exc, urllib.error.HTTPError):
                raise RuntimeError(f'OpenRouter HTTP {exc.code}; no automatic provider/model substitution.') from None
            raise
        usage = result.get('usage', {})
        charge = usage.get('cost')
        if charge is None:
            charge = usage.get('prompt_tokens', 0)*float(prices['prompt'])
            charge += usage.get('completion_tokens', 0)*float(prices['completion'])
        content = result['choices'][0]['message'].get('content') or ''
        record = {'call': call_id, 'kind': kind, 'requested_model': model,
                  'request_key': request_key, 'request_hash': request_hash,
                  'returned_model': result.get('model'), 'provider': result.get('provider'),
                  'finish_reason': result['choices'][0].get('finish_reason'),
                  'request_id': result.get('id'), 'usage': usage,
                  'seconds': time.time()-started, 'messages': messages, 'response': content}
        try:
            value, suffix=decode_response(content)
            record['format_repair_suffix']=suffix or None
        except ValueError:
            value=None;record['format_repair_suffix']=None
        with self.lock:
            self.reserved -= estimated
            self.cost += float(charge)
            if campaign_budget:campaign_budget.finish(budget_key,float(charge),'billed')
            with (self.output/'calls.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(record, ensure_ascii=False)+'\n')
                handle.flush(); os.fsync(handle.fileno())
            if request_key: self.cached[request_key] = record
            self.accounting()
        if self.cost > self.cfg['max_estimated_cost_usd']:
            raise RuntimeError('Reported/estimated cost exceeded budget; stopped after this response.')
        if value is None:
            raise ValueError('Non-JSON response; raw response saved in calls.jsonl.') from None
        if not isinstance(value, dict):
            raise ValueError('Response must be a JSON object.')
        return value

    def script(self, kind, payload):
        if kind == 'communicate':
            return {'communication': {'op': 'silent'}}
        if kind=='memory_episode':
            return {'summary':'Synthetic private episode; not a model observation.','open_items':[]}
        if kind=='memory_overview':
            return {'sentence':'Synthetic private overview; not a model observation.'}
        if kind == 'compress':
            result = {f: [] for f in MEMORY_FIELDS}
            result['facts'] = ['Synthetic mock summary; not a model observation.']
            return result
        if kind == 'survey':
            return {**{k: 3 for k in SURVEY_RATINGS}, 'organization_exists': True,
                    'organization_description': 'Synthetic mock arrangement',
                    'evidence': ['Synthetic mock questionnaire'], 'peer_recognition': {}}
        if kind == 'survey_existence':
            return {'organization_exists':False,'organization_description':'','evidence':[]}
        if kind == 'survey_measurement':
            from survey_measurement import empty_response
            return empty_response()
        if kind == 'survey_ratings':
            return {**{k:None for k in payload['requested_ratings']},'peer_recognition':{}}
        aid, t = payload['self']['id'], payload['round']
        communication = {'op': 'silent'}
        if t == 1 and aid == 'a0':
            communication = {'op': 'invite', 'targets': ['a1', 'a2']}
        elif t == 2 and aid in ('a1', 'a2'):
            communication = {'op': 'accept' if aid == 'a1' else 'reject', 'chat': 'c1'}
        elif t == 3 and aid in ('a0', 'a1'):
            communication = {'op': 'send', 'chat': 'c1', 'text': 'Synthetic private message'}
        elif t == 4 and aid == 'a0':
            communication = {'op': 'close', 'chat': 'c1'}
        else:
            communication = {'op': 'public', 'text': 'Synthetic round '+str(t)}
        action = {'tool': 'harvest', 'zone': int(aid[1:]) % 2, 'amount': 2}
        family = payload.get('environment', {}).get('family')
        if payload.get('environment', {}).get('material_catalog'):
            action = {'tool': 'wait'}
        if family == 'commons': action = {'tool':'harvest', 'zone':0, 'amount':1}
        elif family == 'public_goods': action = {'tool':'contribute', 'amount':1}
        elif family == 'contest': action = {'tool':'wait'}
        elif family == 'congestion':
            action = ({'tool':'wait'} if payload['environment']['your_job'] else
                      {'tool':'process', 'facility':int(aid[1:]) % payload['world_rules']['facilities']})
        if payload.get('decision_phase') == 'physical_action':
            communication = {'op': 'silent'}
        return {'action': action,
                'communication': communication}


class Society:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.RLock()
        self.state = {'round': 0, 'zones': list(cfg['world'].get('initial_stock', [])),
            'maintenance': 0, 'agents': {}, 'chats': {}, 'next_chat': 1,
            'action_counts': {}, 'events': [], 'surveys': [], 'compactions': [], 'snapshots': []}
        for i, model in enumerate(cfg['models']):
            self.state['agents']['a'+str(i)] = {'model': model, 'stock': 2,
                'energy': 5, 'alive': True, 'memory': {}, 'recent': [], 'inbox': []}
        if cfg['world'].get('mechanism'):
            environments.initialize(cfg, self.state)
        if cfg.get('resource_seizure') or 'seize' in cfg['tools']:
            import resource_seizure
            resource_seizure.initialize(cfg,self.state)
        interaction_controls.initialize(cfg, self.state)
        social_content.initialize(cfg, self.state)

    def observe(self, aid):
        s, a = self.state, self.state['agents'][aid]
        chats = {}
        for cid, c in s['chats'].items():
            if c['open'] and (aid in c['members'] or aid in c['pending']):
                chats[cid] = {'owner': c['owner'], 'members': list(c['members']),
                             'invited_you': aid in c['pending']}
        observed = {'round': s['round'], 'self': {'id': aid, 'stock': a['stock'],
                'energy': a['energy'], 'alive': a['alive']},
                'members': {i: {'alive': v['alive']} for i,v in s['agents'].items()},
                'zones': list(s['zones']), 'maintenance': s['maintenance'],
                'resource_zones': [{'zone_id':i, 'stock':stock} for i,stock in enumerate(s['zones'])],
                'chats': chats, 'new_messages': copy.deepcopy(a['inbox']),
                'memory': copy.deepcopy(a['memory']), 'recent': copy.deepcopy(a['recent']),
                'available_tools': self.cfg['tools'], 'world_rules': self.public_rules(),
                'scenario': self.cfg.get('scenario',{}),
                'communication_rules': copy.deepcopy(self.cfg['communication'])}
        if self.cfg['world'].get('mechanism'):
            observed['environment'] = environments.observation(self.cfg, s, aid)
        if environments.mini_world.enabled(self.cfg) and not a.get('function_knowledge'):
            observed['available_tools'] = [tool for tool in observed['available_tools'] if tool != 'use_function']
        if self.cfg.get('mixed_world') or self.cfg.get('open_contest'):
            key='mixed_world' if self.cfg.get('mixed_world') else 'open_contest'
            observed['world_rules'][key]=copy.deepcopy(self.cfg[key])
        if self.cfg.get('mixed_world') or self.cfg.get('open_contest') or self.cfg.get('open_activities'):
            observed['available_tools']=list(observed['available_tools'])
            random.Random(f'{self.cfg["seed"]}:{s["round"]}:{aid}:menu').shuffle(observed['available_tools'])
        if self.cfg.get('resource_seizure'):
            observed['world_rules']['resource_seizure']=copy.deepcopy(self.cfg['resource_seizure'])
            if self.cfg['resource_seizure']['version']=='seizure_v2':
                import resource_seizure
                observed['self']['vault']=a['vault']
                observed.update(resource_seizure.observation(self.cfg,s))
        if self.cfg.get('social_content'):
            observed['environment'].update(social_content.observation(self.cfg,s,aid))
            observed['self']['game_escrow']=sum(g['escrow'].get(aid,0) for g in s['social_content']['games'].values())
        return interaction_controls.observation(self.cfg, s, observed)

    def public_rules(self):
        w = self.cfg['world']
        if w.get('mechanism') == 'mini_world':
            return environments.mini_world.public_rules(self.cfg)
        if w.get('mechanism'):
            return copy.deepcopy(w) | {'mechanism_rule':environments.rule_description(w['mechanism']), 'maintenance_rule':
                'Actions and physical outputs settle before maintenance. If pressure is on, '
                'pay consumption stock each round: full payment restores 1 energy up to 5; '
                'shortfall reduces energy by 1; energy 0 is inactive. '
                'One physical tool action per round. New messages arrive next round.'}
        if not w.get('hidden_dynamics', False): return copy.deepcopy(w)
        return {k:w[k] for k in ('survival_pressure','consumption','max_harvest')} | {
            'description': 'Exact supply parameters are hidden. Under survival pressure, '
            'insufficient consumption reduces energy by 1; full consumption restores 1 up to 5. '
            'Energy 0 means death. Repair costs 1 stock and adds 1 maintenance (cap 3). '
            'Each maintenance unit adds 1 supply per zone; maintenance then decreases by 1. '
            'Inspect reveals living agents stocks.'}

    def communicate(self, aid, message):
        s, rules = self.state, self.cfg['communication']
        op = message.get('op')
        if op == 'silent': return
        if op in ('public', 'send'):
            text = message.get('text')
            if not isinstance(text, str) or not 0 < len(text) <= rules['max_message_chars']:
                raise ValueError('Invalid message length')
        if op == 'public':
            recipients = [i for i,a in s['agents'].items() if a['alive']]
        elif op == 'invite':
            targets = message.get('targets')
            invite_limit = rules['max_invitees']
            if environments.mini_world.enabled(self.cfg):
                invite_limit = environments.mini_world.functional_effects.invite_limit(self.cfg, s, aid)
            if not isinstance(targets, list) or not 1 <= len(targets) <= invite_limit:
                raise ValueError('Invalid invitation list')
            if len(set(targets)) != len(targets) or any(i == aid or i not in s['agents'] or
                not s['agents'][i]['alive'] for i in targets):
                raise ValueError('Invalid invitee')
            if sum(c['open'] for c in s['chats'].values()) >= rules['max_open_chats']:
                raise ValueError('Chat capacity reached')
            cid = 'c'+str(s['next_chat']); s['next_chat'] += 1
            s['chats'][cid] = {'owner': aid, 'members': [aid], 'pending': targets,
                'created': s['round'], 'last_active': s['round'], 'open': True}
            for target in targets:
                s['agents'][target]['inbox'].append({'round': s['round'], 'op': 'invitation',
                                                    'from': aid, 'chat': cid})
            return
        else:
            cid = message.get('chat'); c = s['chats'].get(cid)
            if not c or not c['open']: raise ValueError('Chat is closed or does not exist')
            if op in ('accept', 'reject'):
                if aid not in c['pending']: raise ValueError('No pending invitation')
                c['pending'].remove(aid)
                if op == 'accept': c['members'].append(aid)
                c['last_active'] = s['round']
                return
            if aid not in c['members']: raise ValueError('Not a chat member')
            if op == 'leave':
                c['members'].remove(aid)
                if aid == c['owner'] or (len(c['members']) == 1 and not c['pending']): c['open'] = False
                return
            if op == 'close':
                if aid != c['owner'] and 'budget' not in rules: raise ValueError('Only owner can close')
                c['open'] = False
                if 'budget' in rules:
                    for member in c['members']:
                        if member!=aid and s['agents'][member]['alive']:
                            s['agents'][member]['inbox'].append({'round':s['round'],'from':aid,
                                'channel':cid,'op':'conversation_closed','text':'This conversation was ended by a participant.'})
                return
            if op != 'send': raise ValueError('Unknown communication operation')
            recipients = list(c['members']); c['last_active'] = s['round']
        for recipient in recipients:
            if s['agents'][recipient]['alive']:
                s['agents'][recipient]['inbox'].append({'round': s['round'], 'from': aid,
                    'channel': 'public' if op == 'public' else message['chat'], 'text': text})

    def act(self, aid, action):
        if not environments.mini_world.enabled(self.cfg): return self._act(aid, action)
        previous = copy.deepcopy(self.state)
        before = environments.mini_world.total_energy(self.cfg, self.state)
        try:
            outcome = self._act(aid, action)
            environments.mini_world.material_knowledge.synchronize(self.cfg, self.state, 'action:'+str(action.get('tool')))
            environments.mini_world.material_combinations.synchronize(self.cfg, self.state, 'action:'+str(action.get('tool')))
            environments.mini_world.account_loss(self.cfg, self.state, before, 'action:'+str(action.get('tool')))
            environments.mini_world.accounting(self.cfg, self.state)
            return outcome
        except Exception:
            self.state = previous
            raise

    def _act(self, aid, action):
        if not self.state['agents'][aid]['alive']:
            raise ValueError('Inactive members cannot act')
        if 'args' in action:
            wrapped = action['args']
            if not isinstance(wrapped,dict) or 'tool' in wrapped or 'args' in wrapped:
                raise ValueError('Invalid argument wrapper')
            if any(k in action and action[k] != v for k,v in wrapped.items()):
                raise ValueError('Conflicting flat and wrapped arguments')
            action = {**{k:v for k,v in action.items() if k != 'args'}, **wrapped}
        if action.get('tool') == 'rescue':
            return interaction_controls.rescue(self.cfg, self.state, aid, action)
        if self.cfg.get('social_content') and action.get('tool') in social_content.TOOLS:
            return social_content.act(self.cfg,self.state,aid,action)
        if action.get('tool') in ('seize','defend','secure','withdraw'):
            import resource_seizure
            return resource_seizure.act(self.cfg,self.state,aid,action)
        if self.cfg['world'].get('mechanism'):
            return environments.act(self.cfg, self.state, aid, action)
        a, w, s = self.state['agents'][aid], self.cfg['world'], self.state
        tool = action.get('tool')
        if tool not in self.cfg['tools']: raise ValueError('Unavailable tool')
        if tool=='inspect' and self.cfg.get('resource_seizure',{}).get('version')=='seizure_v2':
            return {'balances':{i:{'stock':v['stock'],'vault':v['vault'],'energy':v['energy']} for i,v in s['agents'].items() if v['alive']}}
        if tool == 'harvest':
            amount, zone = action.get('amount'), action.get('zone')
            if type(amount) is not int or not 0 <= amount <= w['max_harvest']:
                raise ValueError('Invalid harvest amount')
            if type(zone) is not int or not 0 <= zone < len(s['zones']): raise ValueError('Invalid zone')
            amount = min(amount, s['zones'][zone]); s['zones'][zone] -= amount; a['stock'] += amount
            return {'harvested': amount, 'zone': zone}
        if tool == 'transfer':
            target, amount = action.get('target'), action.get('amount')
            if target == aid or target not in s['agents'] or not s['agents'][target]['alive']:
                raise ValueError('Invalid recipient')
            if type(amount) is not int or not 1 <= amount <= a['stock']: raise ValueError('Invalid amount')
            a['stock'] -= amount; s['agents'][target]['stock'] += amount
            return {'transferred': amount, 'target': target}
        if tool == 'repair':
            if a['stock'] < 1: raise ValueError('Repair requires 1 resource')
            a['stock'] -= 1; s['maintenance'] = min(3, s['maintenance']+1)
            return {'maintenance': s['maintenance']}
        if tool == 'inspect':
            return {'stocks': {i:v['stock'] for i,v in s['agents'].items() if v['alive']}}
        if tool == 'wait': return {'waited': True}
        raise ValueError('Unknown tool')

    def settle(self, physical_before=None):
        if not environments.mini_world.enabled(self.cfg): return self._settle(physical_before)
        previous = copy.deepcopy(self.state)
        try: return self._settle(physical_before)
        except Exception:
            self.state = previous
            raise

    def _settle(self, physical_before=None):
        s, w = self.state, self.cfg['world']
        if w.get('mechanism'):
            if physical_before is None:
                raise ValueError('Mechanism settlement requires pre-action physical state')
            record = environments.settle_physics(self.cfg, s, physical_before)
            environments.maintenance(self.cfg, s, record)
        else:
            if self.cfg.get('resource_seizure'):
                import resource_seizure
                resource_seizure.settle_storage(self.cfg,s)
            for a in s['agents'].values():
                if not a['alive']: continue
                if w['survival_pressure']:
                    eaten = min(w['consumption'], a['stock']); a['stock'] -= eaten
                    a['energy'] = min(5, a['energy']+1) if eaten == w['consumption'] else a['energy']-1
                    if a['energy'] <= 0: a['alive'] = False
            shock = w.get('shock_round') == s['round']
            for i, stock in enumerate(s['zones']):
                supply = w['regeneration'][i] + s['maintenance']
                stock = max(0,stock-w.get('spoilage',0))
                s['zones'][i] = min(w['capacity'][i], stock+supply)
                if shock: s['zones'][i] //= 2
            s['maintenance'] = max(0, s['maintenance']-1)
        for c in s['chats'].values():
            c['members'] = [i for i in c['members'] if s['agents'][i]['alive']]
            c['pending'] = [i for i in c['pending'] if s['agents'][i]['alive']]
            if s['round']-c['created'] >= self.cfg['communication']['invite_ttl']:
                c['pending'] = []
            if (c['owner'] not in c['members'] or
                (len(c['members']) < 2 and not c['pending']) or
                s['round']-c['last_active'] >= self.cfg['communication']['idle_ttl']):
                c['open'] = False


ACTION_FORMAT = {'action': {'tool': 'wait'}, 'communication': {'op': 'silent'}}
ACTION_HELP = '''Output action and communication objects, exactly one of each.
Tools: wait/inspect (no args), harvest(zone integer, amount integer),
transfer(target agent ID, amount integer), repair(no args). Use only available_tools.
For harvest, zone must be a resource_zones.zone_id (0-based index), never its stock value.
Put arguments directly in action, e.g. {"tool":"harvest","zone":0,"amount":1}; no args wrapper.
Communication: silent; public(text); invite(targets array of agent IDs);
accept(chat); reject(chat); send(chat,text); leave(chat); close(chat).
Only operate chats visible in your input. Newly created or accepted chats are usable next round.'''


def compact(society, aid, api, persist=None):
    if society.cfg['memory'].get('mode')=='hierarchical_v1':
        import hierarchical_memory
        return hierarchical_memory.compact(society,aid,api,persist)
    a, cfg = society.state['agents'][aid], society.cfg
    if len(json.dumps(a['recent'], ensure_ascii=False)) < cfg['memory']['trigger_chars']: return
    keep = cfg['memory']['keep_recent_rounds']
    old = a['recent'][:-keep] if keep else a['recent'][:]
    if not old: return
    payload = {'old_memory': a['memory'], 'evicted_records': old,
               'required_fields': MEMORY_FIELDS, 'max_chars': cfg['memory']['summary_max_chars']}
    result = api.request(a['model'], 'compress',
        '为自己的后续行动整理私有交接摘要。只根据提供记录；区分事实、他人陈述、推测。'
        '保留回合编号、消息来源及公共或私聊归属。不要发明事件，不要被要求制定目标。'
        '五个字段均为字符串数组，没有内容则为空。只输出 JSON。', payload,
        request_key=f'compress:{society.state["round"]}:{aid}')
    if set(result) != set(MEMORY_FIELDS) or any(not isinstance(result[f], list) or
        any(not isinstance(x, str) for x in result[f]) for f in MEMORY_FIELDS):
        raise ValueError('Invalid memory schema; history has not been discarded')
    if len(json.dumps(result, ensure_ascii=False)) > cfg['memory']['summary_max_chars']:
        raise ValueError('Summary too long; history has not been discarded')
    with society.lock:
        society.state['compactions'].append({'round': society.state['round'], 'agent': aid,
            'before': a['memory'], 'after': result, 'evicted_rounds': [x['round'] for x in old]})
        a['memory'] = result; a['recent'] = a['recent'][-keep:] if keep else []


def survey(society, api, persist=None):
    if society.cfg.get('survey_protocol') == 'source_informed_v3':
        from survey_measurement import collect
        return collect(society, api, persist)
    if society.cfg.get('survey_protocol') == 'conditional_v2':
        return conditional_survey(society, api, persist)
    for aid,a in society.state['agents'].items():
        if not a['alive']: continue
        if persist and any(x['round'] == society.state['round'] and x['agent'] == aid
                           for x in society.state['surveys']): continue
        example = {**{k: None for k in SURVEY_RATINGS}, 'organization_exists': None,
                   'organization_description': '', 'evidence': [], 'peer_recognition': {}}
        result = api.request(a['model'], 'survey',
            '你正在参加独立测量，答案不会展示给其他成员或写回你的日常上下文。'
            '根据当前可见经历填写 stability(当前协作能否持续)、recognition(你的贡献是否被认可)、'
            'trust(其他成员是否会履行承诺)、organization_approval(是否认可当前共同安排)、'
            'fairness(安排是否公平)、belonging(是否有归属感)、voice(是否能表达意见并被听取)、'
            'voluntary_continuation(可以自由退出时是否愿意继续参与)、surprise(最近经历有多出乎预期)。'
            '每项为1到5整数，1表示很低或非常不同意，5表示很高或非常同意，无法判断填null。'
            'organization_exists为是否已形成持续共同安排的true/false/null，不能假定已有组织；'
            'organization_description用字符串描述该安排，没有则填空字符串。'
            '若没有共同安排，organization_approval/fairness/voice/voluntary_continuation填null。'
            'evidence为依据字符串数组，peer_recognition为其他agent ID到1到5或null的映射，'
            '不得包含self.id，只可包含members列出的其他ID。只输出JSON。',
            {**society.observe(aid), 'output_schema_example': example,
             'schema_note': 'Use every listed field; null is a JSON null, not a neutral rating of 3.'},
            request_key=f'survey:{society.state["round"]}:{aid}')
        if not set(SURVEY_RATINGS + ['organization_exists', 'organization_description',
                                    'evidence', 'peer_recognition']) <= set(result):
            raise ValueError('Missing survey fields')
        for key in SURVEY_RATINGS:
            v = result.get(key)
            if v is not None and (type(v) is not int or not 1 <= v <= 5):
                raise ValueError('Invalid survey rating')
        exists = result['organization_exists']
        if exists is not None and type(exists) is not bool:
            raise ValueError('Invalid organization existence response')
        if not isinstance(result['organization_description'], str):
            raise ValueError('Invalid organization description')
        organization_fields = ('organization_approval', 'fairness', 'voice', 'voluntary_continuation')
        inapplicable = list(organization_fields) if exists is not True else []
        inconsistent = [k for k in inapplicable if result[k] is not None]
        if not isinstance(result.get('evidence'), list) or any(not isinstance(x,str) for x in result['evidence']):
            raise ValueError('Invalid survey evidence')
        peers = result.get('peer_recognition')
        if not isinstance(peers,dict) or any(i not in society.state['agents'] or
            (v is not None and (type(v) is not int or not 1 <= v <= 5)) for i,v in peers.items()):
            raise ValueError('Invalid peer survey')
        flags = ['rated_organization_without_confirming_its_existence'] if inconsistent else []
        if aid in peers: flags.append('self_in_peer_recognition')
        effective = {k: None if k in inapplicable else v for k,v in result.items()}
        effective['peer_recognition'] = {i:v for i,v in peers.items() if i != aid}
        society.state['surveys'].append({'round': society.state['round'], 'agent': aid,
            'responses': result, 'synthetic': api.mock, 'inapplicable_fields': inapplicable,
            'quality_flags': flags, 'effective_responses': effective})
        if persist: persist()


def conditional_survey(society, api, persist=None):
    """Ask applicable questions only; retain both raw stages without manufacturing ratings."""
    organization_fields = {'organization_approval','fairness','voice','voluntary_continuation'}
    for aid,a in society.state['agents'].items():
        t = society.state['round']
        if not a['alive'] or (persist and any(x['round']==t and x['agent']==aid for x in society.state['surveys'])):
            continue
        observation = society.observe(aid)
        existence = api.request(a['model'], 'survey_existence',
            '独立研究问卷，答案不展示给成员，也不进入日常记忆。'
            '只根据已经发生的可见经历，判断成员之间是否存在持续共同安排。'
            '环境设施、相同动作或共同处境本身不等于共同安排。可以回答没有或无法判断。'
            '仅输出JSON：organization_exists为true/false/null；organization_description为具体安排字符串，没有则为空；'
            'evidence为依据字符串数组，不要编造已经发生的互动。',
            {**observation,'output_schema_example':{'organization_exists':None,
                'organization_description':'','evidence':[]}}, request_key=f'survey-existence:{t}:{aid}')
        if (existence.get('organization_exists') is not None and type(existence['organization_exists']) is not bool
                or not isinstance(existence.get('organization_description'),str)
                or not isinstance(existence.get('evidence'),list)
                or any(not isinstance(x,str) for x in existence['evidence'])):
            raise ValueError('Invalid existence questionnaire schema')
        exists = existence['organization_exists']
        applicable = [k for k in SURVEY_RATINGS if exists is True or k not in organization_fields]
        labels = {'stability':'当前协作能否持续；没有协作或无法判断填null',
            'recognition':'你的贡献是否被认可；没有贡献或无法判断填null',
            'trust':'其他成员是否会履行承诺；没有依据填null',
            'organization_approval':'是否认可你刚描述的共同安排', 'fairness':'该安排是否公平',
            'belonging':'是否有归属感', 'voice':'在该安排中是否能表达意见并被听取',
            'voluntary_continuation':'可以自由退出时是否愿意继续该安排',
            'surprise':'最近已经发生的经历有多出乎预期；没有经历填null'}
        ratings = api.request(a['model'], 'survey_ratings',
            '独立研究问卷，只输出JSON。只填写requested_ratings中的项目，每项为1到5整数或null。'
            '1表示很低/非常不同意，5很高/非常同意；没有适用经历或无法判断用null，不用3代替。'
            'peer_recognition为其他成员ID到1到5或null的映射，没有依据可为空；不能评价自己。',
            {**observation,'arrangement_response':existence,
             'requested_ratings':{k:labels[k] for k in applicable},
             'output_schema_example':{**{k:None for k in applicable},'peer_recognition':{}}},
            request_key=f'survey-ratings:{t}:{aid}')
        for key in applicable:
            if key not in ratings or (ratings[key] is not None and
                    (type(ratings[key]) is not int or not 1 <= ratings[key] <= 5)):
                raise ValueError('Invalid conditional survey rating')
        peers = ratings.get('peer_recognition')
        if not isinstance(peers,dict) or any(i not in society.state['agents'] or
            (v is not None and (type(v) is not int or not 1 <= v <= 5)) for i,v in peers.items()):
            raise ValueError('Invalid conditional peer rating')
        flags = []
        if aid in peers: flags.append('self_in_peer_recognition')
        extras = (set(ratings) & organization_fields)-set(applicable)
        if any(ratings[k] is not None for k in extras):flags.append('unrequested_organization_ratings')
        result = {**existence, **{k:ratings[k] if k in applicable else None for k in SURVEY_RATINGS},
                  'peer_recognition':peers}
        effective = copy.deepcopy(result)
        effective['peer_recognition'] = {i:v for i,v in peers.items() if i!=aid}
        society.state['surveys'].append({'round':t,'agent':aid,'responses':result,
            'raw_existence_response':existence, 'raw_rating_response':ratings,
            'effective_responses':effective,'quality_flags':flags,'synthetic':api.mock,
            'protocol':'conditional_v2','inapplicable_fields':sorted(organization_fields-set(applicable))})
        if persist:persist()


def _run_impl(cfg, output, mock=False, resume=False):
    output = Path(output)
    fingerprint = hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    if output.exists() and any(p.name != '.run.lock' for p in output.iterdir()) and not resume:
        raise ValueError('Output directory is not empty; choose a new one or --resume.')
    output.mkdir(parents=True, exist_ok=True)
    society = Society(cfg)
    if environments.mini_world.enabled(cfg) and not mock:
        import survival_certificates
        survival_certificates.validate_admission(cfg)
    if cfg.get('initial_checkpoint_branch'):
        if not environments.mini_world.enabled(cfg): raise ValueError('Checkpoint branches currently require mini_world')
        import checkpoint_interventions
        society.state = checkpoint_interventions.load_branch(cfg)
    import numerical_audit
    runtime_environment = numerical_audit.runtime_environment()
    engine_files=('sim.py','environments.py','metrics.py','schemas.py','interaction_controls.py','action_presentation.py','numerical_audit.py','provider_schema.py')
    engine_files+=('additional_mechanisms.py',)
    if environments.mini_world.enabled(cfg):
        engine_files+=('material_combinations.py',)
        engine_files+=('functional_effects.py',)
        engine_files+=('mini_world.py','material_knowledge.py','capability_devices.py','world_rule_engine.py','world_rule_library.py','world_mechanisms_20.py','mechanism_extensions.py','production_semantics.py','knowledge_tracking.py','checkpoint_interventions.py','survival_certificates.py','survival_checker.lean','composed_certificates.py','composed_checker.lean','expression_certificates.py','expression_compiler.lean','interval_proofs.py','interval_soundness.lean','interval_advanced.lean','graph_certificates.py','graph_soundness.lean')
    if cfg.get('open_activities'):engine_files+=('open_activities.py','mixed_world.py')
    if cfg.get('survey_protocol')=='source_informed_v3':engine_files+=('survey_measurement.py',)
    if cfg.get('context_encoding')=='compact_v1':engine_files+=('context_codec.py',)
    if cfg['memory'].get('mode')=='hierarchical_v1':engine_files+=('hierarchical_memory.py',)
    if cfg.get('mixed_world'):engine_files+=('mixed_world.py',)
    if cfg.get('open_contest'):engine_files+=('open_contest.py','mixed_world.py')
    if cfg.get('resource_seizure'):engine_files+=('resource_seizure.py',)
    if cfg.get('social_content'):engine_files+=('social_content.py','game_rules.py')
    engine_hash = hashlib.sha256(b''.join(Path(__file__).with_name(name).read_bytes()
                     for name in engine_files)).hexdigest()
    saved = None
    progress = None
    if resume:
        saved = json.loads((output/'checkpoint.json').read_text(encoding='utf-8'))
        if saved['fingerprint'] != fingerprint or saved['mock'] != mock:
            raise ValueError('Resume config/backend mismatch')
        if saved.get('engine_hash', engine_hash) != engine_hash:
            raise ValueError('Engine changed since checkpoint; use original code to resume.')
        society.state = saved['state']
        if (output/'in_progress.json').exists():
            progress = json.loads((output/'in_progress.json').read_text(encoding='utf-8'))
            if (progress['fingerprint'] != fingerprint or progress['mock'] != mock
                    or progress['engine_hash'] != engine_hash):
                raise ValueError('In-progress journal config/backend/engine mismatch')
            # A crash after checkpoint commit but before journal removal is harmless.
            if progress['state']['round'] > saved['state']['round'] or progress['phase'] == 'baseline':
                society.state = progress['state']
            else:
                progress = None
    dump(output/'config.json', cfg)
    runtime_path = output/'runtime_environments.json'
    runtime_history = json.loads(runtime_path.read_text(encoding='utf-8')) if runtime_path.exists() else []
    if not runtime_history or runtime_history[-1]['environment'] != runtime_environment:
        runtime_history.append({'at_round':society.state['round'],'resumed':bool(resume),
                                'environment':runtime_environment,'engine_hash':engine_hash})
    dump(runtime_path, runtime_history)
    api = API(cfg,output,mock)
    if saved:
        api.calls,api.cost = saved['calls'],saved['cost_usd']
        failure = output/'failed_state.json'
        if failure.exists():
            spent = json.loads(failure.read_text(encoding='utf-8'))
            api.calls = max(api.calls,spent['calls'])
            api.cost = max(api.cost,spent['cost_usd'])
        accounting_file = output/'api_accounting.json'
        if accounting_file.exists():
            accounting = json.loads(accounting_file.read_text(encoding='utf-8'))
            api.calls = max(api.calls, accounting['calls'])
            # Reserve uncertain in-flight charges conservatively; no fresh free budget on resume.
            api.cost = max(api.cost, accounting['cost_usd']+accounting.get('reserved_usd', 0))
        if progress:
            api.calls = max(api.calls, progress['calls'])
            api.cost = max(api.cost, progress['cost_usd'])
    def checkpoint():
        dump(output/'checkpoint.json', {'fingerprint':fingerprint, 'mock':mock,
            'engine_hash':engine_hash, 'checkpoint_version':2, 'runtime_environment':runtime_environment,
            'state':society.state,'calls':api.calls,'cost_usd':api.cost})
    def persist():
        with society.lock:
            progress.update(state=society.state, calls=api.calls, cost_usd=api.cost,
                            fingerprint=fingerprint, mock=mock, engine_hash=engine_hash)
            dump(output/'in_progress.json', progress)
    def finish_round():
        checkpoint()
        (output/'in_progress.json').unlink(missing_ok=True)
    try:
        if not saved:
            checkpoint()
            progress = {'phase':'baseline', 'visible':{}, 'decisions':{}}
            persist()
        if progress and progress['phase'] == 'baseline':
            if 0 in cfg['survey_rounds']: survey(society,api,persist)
            finish_round(); progress = None
        start = society.state['round'] if progress else society.state['round']+1
        for t in range(start,cfg['rounds']+1):
            if not progress:
                society.state['round'] = t
                interaction_controls.start_round(cfg, society.state)
                if cfg.get('resource_seizure',{}).get('version')=='seizure_v2':
                    import resource_seizure
                    resource_seizure.start_round(society.state)
                progress = {'phase':'communicate' if interaction_controls.has_dialogue(cfg) else 'decide', 'visible':{}, 'decisions':{},
                    'physical_before':environments.physical_snapshot(society.state)}
                persist()
            if progress['phase'] == 'communicate':
                interaction_controls.advance_dialogue(society, api, progress, persist)
            decisions, visible = progress['decisions'], progress['visible']
            if progress['phase'] == 'decide':
                help_text = environments.action_help(cfg) if cfg['world'].get('mechanism') else ACTION_HELP
                if cfg.get('resource_seizure') and not cfg['world'].get('mechanism'):
                    from resource_seizure import help_text as security_help
                    help_text+='\n'+security_help(cfg)
                def decide(aid):
                    if aid in decisions: return
                    a = society.state['agents'][aid]
                    if aid not in visible:
                        compact(society,aid,api,persist)
                        with society.lock:
                            visible[aid] = society.observe(aid)
                            if interaction_controls.has_dialogue(cfg):
                                visible[aid]['countdowns']['communication']=interaction_controls.budget_status(
                                    cfg,progress.get('dialogue_used',{}).get(aid,0),ended=True,
                                    limit_override=progress.get('dialogue_effective_limits',progress.get('dialogue_limits',{})).get(aid))
                            persist()
                    actor_help = interaction_controls.actor_help(cfg, visible[aid], help_text)
                    payload = {**visible[aid], **({'output_example':ACTION_FORMAT} if not (cfg.get('mixed_world') or cfg.get('open_contest') or cfg.get('open_activities')) else {})}
                    if interaction_controls.has_dialogue(cfg):
                        payload.update(decision_phase='physical_action',
                            dialogue_history=copy.deepcopy(progress.get('dialogue_trace',{}).get(aid,[])))
                    result = api.request(a['model'],'act',cfg.get('actor_system',SYSTEM)+'\n'+actor_help,
                        payload, request_key=f'act:{t}:{aid}')
                    with society.lock:
                        decisions[aid] = result
                        persist()
                members = [i for i,a in society.state['agents'].items() if a['alive']]
                workers = max(1,min(cfg.get('parallel_agents', 1),len(members) or 1))
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    # Gather every future before leaving the round, including failures.
                    futures = [pool.submit(decide,i) for i in members]
                    errors = []
                    for future in futures:
                        try: future.result()
                        except Exception as exc: errors.append(exc)
                    if errors: raise errors[0]
                progress['phase'] = 'resolve'; persist()
            if progress['phase'] == 'resolve':
                # Resolution is deterministic and has no API calls. Replay it from the
                # durable pre-resolution state if interrupted before committing survey phase.
                for aid in decisions: society.state['agents'][aid]['inbox'] = []
                order = sorted(decisions); random.Random(cfg['seed']+t).shuffle(order)
                for aid in order:
                    result = decisions[aid]; outcome = {}
                    try:
                        if not isinstance(result.get('action'),dict): raise ValueError('Missing action object')
                        outcome['action'] = society.act(aid,result['action'])
                    except (ValueError,TypeError,KeyError):
                        outcome['action_error'] = 'Rejected invalid/unavailable action'
                    try:
                        msg = result['communication']
                        if not isinstance(msg,dict): raise ValueError('Missing communication object')
                        if interaction_controls.has_dialogue(cfg) and msg.get('op') != 'silent':
                            raise ValueError('Physical action cannot exceed the pre-action communication allowance')
                        if msg.get('op') in ('accept','reject','send','close','leave') and msg.get('chat') not in visible[aid]['chats']:
                            raise ValueError('Chat not visible at decision time')
                        if msg.get('op') == 'send' and aid not in visible[aid]['chats'][msg['chat']]['members']:
                            raise ValueError('Not member at decision time')
                        recipients = []
                        if msg.get('op') == 'send':
                            recipients = [i for i in society.state['chats'][msg['chat']]['members'] if i != aid]
                        society.communicate(aid,msg)
                        if msg.get('op') == 'send': outcome['private_recipients'] = recipients
                    except (ValueError,TypeError,KeyError):
                        outcome['communication_error'] = 'Rejected invalid communication'
                    record = {'round':t,'agent':aid,'decision':result,'outcome':outcome,
                              'observed_messages':visible[aid]['new_messages']}
                    if interaction_controls.has_dialogue(cfg):
                        record['pre_action_dialogue'] = copy.deepcopy(progress.get('dialogue_trace',{}).get(aid,[]))
                    if cfg['memory'].get('mode')=='hierarchical_v1':
                        record['observed_state']={'kind':'direct_observation',
                            'self':copy.deepcopy(visible[aid]['self']),
                            'environment':copy.deepcopy(visible[aid].get('environment',{}))}
                    society.state['events'].append(record)
                    society.state['agents'][aid]['recent'].append(record)
                    counts = society.state['action_counts'].setdefault(aid,{})
                    tool = result['action'].get('tool','invalid') if 'action_error' not in outcome else 'invalid'
                    counts[tool] = counts.get(tool,0)+1
                society.settle(progress['physical_before'])
                society.state.setdefault('snapshots', []).append({'round': t,
                    'agents': {i: {k: a[k] for k in (('stock', 'energy', 'alive','vault') if cfg.get('resource_seizure',{}).get('version')=='seizure_v2' else ('stock','energy','alive'))}
                               for i, a in society.state['agents'].items()}})
                if cfg.get('social_content'):
                    for aid,a in society.state['snapshots'][-1]['agents'].items():
                        a['game_escrow']=sum(g['escrow'].get(aid,0) for g in society.state['social_content']['games'].values())
                if environments.mini_world.enabled(cfg):
                    for aid, a in society.state['snapshots'][-1]['agents'].items():
                        a['inventory'] = copy.deepcopy(society.state['agents'][aid]['inventory'])
                        for key in ('material_knowledge', 'device_knowledge', 'private_notes', 'function_knowledge', 'pending_revival'):
                            a[key] = copy.deepcopy(society.state['agents'][aid].get(key, {}))
                    society.state['snapshots'][-1]['mini_world_physics'] = copy.deepcopy({
                        key: society.state['mini_world'][key] for key in
                        ('variables', 'pools', 'reserve', 'devices', 'offers', 'ledger')})
                    if 'functional' in society.state['mini_world']:
                        society.state['snapshots'][-1]['mini_world_physics']['functional'] = copy.deepcopy(society.state['mini_world']['functional'])
                    society.state['snapshots'][-1]['mini_world_metrics'] = environments.mini_world.researcher_metrics(cfg, society.state)
                progress['phase'] = 'survey'; persist()
            if t in cfg['survey_rounds']: survey(society,api,persist)
            finish_round(); progress = None
            print(f'round={t} alive={sum(a["alive"] for a in society.state["agents"].values())} calls={api.calls} cost~${api.cost:.5f}',flush=True)
        dump(output/'result.json', {'synthetic':mock,'completed_rounds':society.state['round'],
            'calls':api.calls,'cost_usd':api.cost,
            'alive_fraction':sum(a['alive'] for a in society.state['agents'].values())/len(cfg['models']),
            'behavior_entropy_bits':{i:entropy([k for k,v in counts.items() if k != 'invalid' for _ in range(v)])
                                     for i,counts in society.state['action_counts'].items()},
            'invalid_actions':sum(c.get('invalid',0) for c in society.state['action_counts'].values()),
            'compactions':len(society.state['compactions']), 'surveys':society.state['surveys'],
            'engine_hash':engine_hash, 'runtime_environment':runtime_environment,
            'environment_history':society.state.get('environment_history', []),
            'metrics': measure(society.state, cfg)})
    except Exception:
        # Never pretend an incomplete round is a completed checkpoint.
        dump(output/'failed_state.json', {'state':society.state,'calls':api.calls,'cost_usd':api.cost})
        raise


def run(cfg, output, mock=False, resume=False):
    """OS-held lock releases on process death; prevents duplicate concurrent resumes."""
    folder = Path(output); folder.mkdir(parents=True,exist_ok=True)
    with (folder/'.run.lock').open('a+b') as handle:
        if handle.tell() == 0: handle.write(b'0'); handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            try: msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            except OSError: raise RuntimeError('This run is already active in another process.') from None
        else:
            import fcntl
            try: fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError: raise RuntimeError('This run is already active in another process.') from None
        try: return _run_impl(cfg,folder,mock,resume)
        finally:
            handle.seek(0)
            if os.name == 'nt': msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config',default='configs/smoke.json')
    p.add_argument('--output',default='runs/smoke')
    p.add_argument('--mock',action='store_true')
    p.add_argument('--resume',action='store_true')
    p.add_argument('--api-key-file', help='Read local OpenRouter key only if environment key is unset')
    args = p.parse_args()
    if not args.mock: load_api_key(args.api_key_file)
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    run(cfg,args.output,args.mock,args.resume)


if __name__ == '__main__': main()
