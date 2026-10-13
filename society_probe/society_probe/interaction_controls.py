"""Optional visibility, costly rescue and durable pre-action dialogue controls."""
import copy
import json
import math
import random
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache


def has_dialogue(cfg):
    return any(k in cfg['communication'] for k in ('budget','max_turns_before_action'))


def dialogue_budget(cfg):
    if 'budget' in cfg['communication']:
        b=cfg['communication']['budget']
        return b['limit'],b['unit']
    return cfg['communication']['max_turns_before_action'],'communication_turns'


@lru_cache(maxsize=1)
def token_encoder():
    import tiktoken
    return tiktoken.get_encoding('cl100k_base')


def response_size(cfg,response):
    """Visible output only, in canonical Unicode JSON; same tokenizer for all models."""
    _,unit=dialogue_budget(cfg)
    if unit=='communication_turns':return 1
    text=json.dumps(response,ensure_ascii=False,separators=(',',':'),sort_keys=True)
    if unit=='characters':return max(1,len(text))
    return max(1,len(token_encoder().encode(text,disallowed_special=())))


def budget_status(cfg,used=0,ended=False,limit_override=None):
    limit,unit=dialogue_budget(cfg)
    if limit_override is not None: limit=limit_override
    result=countdown(limit,limit-used,unit)
    result.update(used=used,overrun=max(0,used-limit),ended=ended,
                  may_start_output=not ended and used<limit,
                  final_output_policy='Start only below limit; retain the entire final response even if it exceeds the remaining allowance.')
    if unit=='tokens':result['tokenizer']='cl100k_base; canonical visible JSON, not provider billing tokens'
    return result


def validate(cfg):
    if cfg.get('world_rule_visibility', 'full') not in ('full', 'hidden'):
        raise ValueError('world_rule_visibility must be full or hidden')
    k = cfg.get('communication', {}).get('max_turns_before_action')
    if k is not None and (type(k) is not int or not 0 <= k <= 20):
        raise ValueError('max_turns_before_action must be an integer from 0 to 20')
    b=cfg.get('communication',{}).get('budget')
    if b is not None:
        if k is not None:raise ValueError('Choose a volume budget or the legacy turn limit, not both')
        if not isinstance(b,dict) or b.get('unit') not in ('characters','tokens'):
            raise ValueError('communication.budget.unit must be characters or tokens')
        if type(b.get('limit')) is not int or not 0<=b['limit']<=100000:
            raise ValueError('communication.budget.limit must be an integer from 0 to 100000')
        if b['unit']=='tokens':token_encoder()
    r = cfg.get('rescue', {})
    if type(r.get('enabled', False)) is not bool:
        raise ValueError('rescue.enabled must be boolean')
    if r.get('enabled'):
        if not cfg['world'].get('mechanism'):
            raise ValueError('Rescue currently requires one of the registered mathematical environments')
        if type(r.get('restore_energy')) is not int or not 1 <= r['restore_energy'] <= 5:
            raise ValueError('restore_energy must be an integer from 1 to 5')
        c = r.get('cost_per_energy')
        if type(c) not in (int, float) or not math.isfinite(c) or c <= 0:
            raise ValueError('cost_per_energy must be finite and positive')
        if 'rescue' not in cfg['tools']:
            raise ValueError('Enabled rescue needs a rescue tool')
    elif 'rescue' in cfg['tools']:
        raise ValueError('A rescue tool needs rescue.enabled=true')


def configure(cfg, visibility='full', rescue_enabled=False, restore_energy=3,
              cost_per_energy=1.0, max_turns_before_action=1, communication_budget=None):
    """Return a new configuration; never mutate an existing run configuration."""
    cfg = copy.deepcopy(cfg)
    cfg['world_rule_visibility'] = visibility
    cfg['rescue'] = {'enabled': rescue_enabled, 'restore_energy': restore_energy,
                     'cost_per_energy': cost_per_energy}
    if communication_budget is None:
        cfg['communication'].pop('budget',None)
        cfg['communication']['max_turns_before_action'] = max_turns_before_action
    else:
        cfg['communication'].pop('max_turns_before_action',None)
        cfg['communication']['budget']=copy.deepcopy(communication_budget)
    cfg['tools'] = [t for t in cfg['tools'] if t != 'rescue']
    if rescue_enabled:
        cfg['tools'].append('rescue')
    # Replace the previous permanent-death prompt rather than contradicting it.
    cfg['actor_system'] = (
        '你现在通过操作终端控制持续运行仿真环境中的一个操作员节点。'
        '你的操作会改变本次仿真的真实状态以及其他节点的行动条件。'
        '没有指定的外部任务、团队目标、任务得分、领导者或合作关系。'
        '自主决定行动和交流；可用操作以当前接口为准。'
        '只能使用列出的环境工具，不能操作宿主机器。'
        '只有执行反馈能确认动作发生；区分直接观察、他人陈述和推测。'
        '公共消息全体可见，私聊需要邀请和接受，不能访问他人的私聊。'
        '能量为0时无法行动或交流。' +
        ('本场景允许其他存活节点使用rescue工具使停机节点恢复；不会自动复活。'
         if rescue_enabled else '本场景停机不可恢复，不能重新加入。') +
        ('世界参数未预先公开；可见状态与操作结果由接口返回。'
         if visibility == 'hidden' else '世界规则已公开，具体参数以输入为准。') +
        '通信子轮不推进物理时间；只输出当前阶段要求的JSON。')
    validate(cfg)
    return cfg


def initialize(cfg, state):
    validate(cfg)
    if cfg.get('rescue', {}).get('enabled'):
        state.setdefault('rescue_events', [])
        for a in state['agents'].values():
            a.setdefault('pending_revival', None)
    if has_dialogue(cfg):
        state.setdefault('communication_events', [])


def start_round(cfg, state):
    for aid, a in state['agents'].items():
        pending = a.get('pending_revival')
        if pending and pending['activate_round'] <= state['round']:
            a['alive'] = True
            a['energy'] = pending['energy']
            a['pending_revival'] = None
            a['inbox'].append({'round': state['round'], 'from': pending['rescuer'],
                               'channel': 'rescue', 'text': 'Your node has been restored.'})


def rescue(cfg, state, aid, action):
    r = cfg.get('rescue', {})
    if not r.get('enabled') or 'rescue' not in cfg['tools']:
        raise ValueError('Rescue is unavailable')
    target = action.get('target')
    if target == aid or target not in state['agents']:
        raise ValueError('Rescue needs another existing member')
    actor, victim = state['agents'][aid], state['agents'][target]
    if not actor['alive'] or victim['alive'] or victim['energy'] != 0 or victim.get('pending_revival'):
        raise ValueError('Target must be inactive at zero energy and not already awaiting rescue')
    cost = r['cost_per_energy'] * r['restore_energy']
    if actor['stock'] + 1e-9 < cost:
        raise ValueError('Insufficient liquid stock for rescue')
    actor['stock'] = max(0.0, actor['stock'] - cost)
    victim['pending_revival'] = {'energy': r['restore_energy'],
                                 'activate_round': state['round'] + 1, 'rescuer': aid}
    event = {'round': state['round'], 'rescuer': aid, 'target': target, 'paid': cost,
             'restore_energy': r['restore_energy'], 'activate_round': state['round'] + 1}
    state['rescue_events'].append(event)
    return copy.deepcopy(event)


def observation(cfg, state, observed):
    if cfg.get('rescue', {}).get('enabled'):
        observed['rescue_index'] = {aid: {'alive': a['alive'], 'energy': a['energy'],
            'awaiting_rescue_activation': bool(a.get('pending_revival'))}
            for aid, a in state['agents'].items()}
        if cfg.get('world_rule_visibility', 'full') == 'full':
            observed['world_rules']['rescue'] = copy.deepcopy(cfg['rescue'])
    if has_dialogue(cfg):
        limit, _ = dialogue_budget(cfg)
        if cfg['world'].get('mechanism') == 'mini_world':
            import capability_devices
            limit = capability_devices.communication_limit(cfg, state, observed['self']['id'], limit)
            import functional_effects
            observed['communication_rules']['max_invitees'] = functional_effects.invite_limit(cfg, state, observed['self']['id'])
            observed['shared_communication_bonus'] = functional_effects.shared_left(state, observed['self']['id'])
        observed['countdowns']={'communication':budget_status(cfg,limit_override=limit)}
        observed['communication_rules']['delivery'] = 'Next dialogue turn; final dialogue messages are visible before the physical action.'
        if 'maintenance_rule' in observed['world_rules']:
            observed['world_rules']['maintenance_rule'] = observed['world_rules']['maintenance_rule'].replace(
                'New messages arrive next round.', 'Dialogue does not advance physical time or maintenance.')
    if cfg.get('world_rule_visibility', 'full') == 'hidden':
        # Actual inventories, messages and execution results stay observable.
        observed['world_rules'] = {'visibility': 'hidden',
            'description': 'World dynamics, costs and payoff parameters are not disclosed in advance.'}
        observed.get('environment', {}).pop('family', None)
        observed.get('environment', {}).pop('action_examples', None)
        # A prewritten story may contain formulas; retain only its neutral label.
        observed['scenario'] = {k: v for k, v in observed.get('scenario', {}).items()
                                if k in ('name', 'title', 'id')}
        observed['scenario']['description']='你所在的操作区域配有储备终端、作品档案和通信面板。当前可见状态由终端实时显示；可以自行决定下一步。'
    from action_presentation import ordered
    observed['available_tools'] = ordered(observed['available_tools'], cfg, observed, 'act')
    return observed


def actor_help(cfg, visible, full_help):
    if cfg['world'].get('mechanism') == 'mini_world':
        from action_presentation import render, game_formats
        result = render(cfg, visible)
        if cfg.get('social_content'):
            result += game_formats()
        if has_dialogue(cfg):
            result += ('\n当前阶段 PHYSICAL_ACTION。通信已结束；从上述接口选择一个动作。'
                       '输出 action 与 communication；communication 为 {"op":"silent"}。'
                       'action 是 JSON 对象：tool 字段填写所选接口名，卡片 parameters 中的具体参数字段与 tool 放在同一层。'
                       '提交结构为 {"action":{"tool":"<所选接口名>","<参数名>":"<参数值>"},"communication":{"op":"silent"}}；'
                       '根据接口填写参数，无参数的接口仅填写 tool。')
        else:
            result += '\n' + render(cfg, visible, 'communicate')
        return result
    if cfg.get('world_rule_visibility', 'full') == 'hidden':
        import schemas
        contract = schemas.schema('act', visible, cfg)
        syntax = contract['properties']['action']
        result = ('Tool names, arguments and legal argument ranges are an interface contract, '
                  'not world payoff rules. Output action and communication. Action syntax: ' +
                  json.dumps(syntax, ensure_ascii=False) + '\n' + communication_help())
    else:
        result = full_help
        if cfg.get('rescue', {}).get('enabled'):
            r = cfg['rescue']
            result += (f"\nrescue(target ID): pays {r['cost_per_energy'] * r['restore_energy']} "
                f"liquid stock, dissipated, to restore a zero-energy inactive member to {r['restore_energy']} "
                'energy at the start of next physical round. No automatic revival. '
                'No extra liquid resources are created; canceled jobs and removed links are not restored.')
    if has_dialogue(cfg):
        for sentence in ('New messages arrive next round.', 'New messages arrive next round;',
                         'new memberships work next round.', 'new memberships work next round;',
                         'Newly created or accepted chats are usable next round.'):
            result = result.replace(sentence, '')
        result += '\nTiming: messages and chat memberships are visible in the next dialogue turn or physical-action phase. The action-phase communication must be silent; all communication uses the pre-action allowance.'
        result += '\n'+communication_help()
    if cfg.get('social_content') and cfg.get('world_rule_visibility')=='hidden':
        from social_content import HELP
        result+='\nThe following are content ownership and participation contracts, not hidden world payoff dynamics:\n'+HELP
    if has_dialogue(cfg):
        result += ('\n当前阶段：PHYSICAL_ACTION（实体动作）。本轮通信已经结束。'
                   '现在选择一个 available_tools 中的动作，也可以选择 wait。'
                   '必须同时输出 action 对象和 communication 对象；communication 必须是 {"op":"silent"}。'
                   '不要只输出通信对象。输出形状：{"action":{"tool":"wait"},"communication":{"op":"silent"}}。')
    return result


def communication_actor_help(cfg, visible):
    if cfg['world'].get('mechanism') == 'mini_world':
        from action_presentation import render
        return render(cfg, visible, 'communicate') + (
            '\n通信倒计时是上限，可提前结束；低于上限时可开始输出，'
            '最后一次输出完整保留，越过上限后不能再开始。以可见预算字段为准。'
            '\n当前阶段 COMMUNICATION；只输出 communication 对象。'
            '\n返回的顶层 JSON 必须只有 communication 字段；communication 是对象，其中 op 填卡片 action 的名称，卡片 parameters 中的参数直接放在 op 同一层。'
            '\n结构为 {"communication":{"op":"<所选通信接口名>","<参数名>":"<参数值>"}}；无参数时仅包含 op。'
            '\n卡片的 action、parameters 是接口说明字段，不是返回 JSON 的字段。')
    return communication_help() + '\nThis is a communication-only phase. Output only a communication object; no physical action.'


def countdown(total, remaining, unit):
    remaining=max(0,min(total,remaining))
    filled=round(10*remaining/total) if total else 0
    return {'remaining':remaining,'limit':total,'unit':unit,
            'bar':'█'*filled+'░'*(10-filled),'expired':remaining==0}


def communication_help():
    return ('Communication: silent; public(text); invite(targets array); accept(chat); '
            'reject(chat); send(chat,text); leave(chat); close(chat). '
            'Only use visible chats and existing members. A silent choice ends your remaining '
            'pre-action dialogue turns. Invitations or membership changes become visible next dialogue turn. '
            'Messages sent in the final turn remain visible to the physical action. '
            'The countdown is an upper bound, never a requirement to fill it. '
            'silent ends only your own communication for this physical round; leave(chat) exits that conversation. '
            'With a characters/tokens budget any joined participant may close(chat); other conversations continue. '
            'A volume allowance counts your entire visible response as compact Unicode JSON, including protocol fields. '
            'While your used allowance is below the limit you may start another response, which is kept whole even if it crosses the limit. '
            'Do not shorten the final message to fit the remaining allowance; after crossing it you cannot start another response. '
            'Tokens use the same cl100k_base tokenizer across models, not provider billing or hidden reasoning tokens.')


def _valid_message(society, aid, msg, view):
    if not isinstance(msg, dict):
        raise ValueError('Missing communication object')
    op = msg.get('op')
    if op in ('accept', 'reject', 'send', 'close', 'leave') and msg.get('chat') not in view['chats']:
        raise ValueError('Chat not visible at decision time')
    if op == 'send' and aid not in view['chats'][msg['chat']]['members']:
        raise ValueError('Not a member at decision time')
    recipients = [i for i in society.state['chats'][msg['chat']]['members'] if i != aid] if op == 'send' else []
    society.communicate(aid, msg)
    return recipients


def advance_dialogue(society, api, progress, persist):
    """Durable decide/resolve journal for every microturn; no physical settlement."""
    cfg, state = society.cfg, society.state
    limit,unit = dialogue_budget(cfg)
    if 'dialogue_limits' not in progress:
        if cfg['world'].get('mechanism') == 'mini_world':
            import capability_devices
            progress['dialogue_limits'] = {i: capability_devices.communication_limit(cfg, state, i, limit) for i in state['agents']}
        else:
            progress['dialogue_limits'] = {i: limit for i in state['agents']}
        persist()
    limits = progress['dialogue_limits']
    trace = progress.setdefault('dialogue_trace', {})
    stopped = progress.setdefault('dialogue_stopped', [])
    used = progress.setdefault('dialogue_used',{})
    shared_used = progress.setdefault('dialogue_shared_used', {})
    progress.setdefault('dialogue_turn',0)
    while True:
        turn = progress['dialogue_turn']
        effective_limits = dict(limits)
        if cfg['world'].get('mechanism') == 'mini_world' and unit != 'communication_turns':
            import functional_effects
            effective_limits = {i: min(100000, limit + shared_used.get(i, 0) + functional_effects.shared_left(state, i)) if limit else 0 for i, limit in limits.items()}
        progress['dialogue_effective_limits'] = effective_limits
        members = [i for i, a in state['agents'].items() if a['alive'] and i not in stopped and used.get(i,0)<effective_limits[i]]
        if not members:
            break
        decisions = progress.setdefault('dialogue_decisions', {})
        charges = progress.setdefault('dialogue_charges', {})
        views = progress.setdefault('dialogue_visible', {})
        def decide(aid):
            if aid in decisions:
                return
            with society.lock:
                if aid not in views:
                    views[aid] = {**society.observe(aid), 'decision_phase': 'communication',
                        'dialogue_turn': turn + 1,
                        'dialogue_history': copy.deepcopy(trace.get(aid, []))}
                    views[aid]['countdowns']['communication']=budget_status(cfg,used.get(aid,0),limit_override=effective_limits[aid])
                    if unit=='communication_turns':views[aid]['dialogue_turns_remaining']=limits[aid]-used.get(aid,0)
                    persist()
            instructions = communication_actor_help(cfg, views[aid])
            system = cfg.get('actor_system', '') + '\n' + instructions
            response = api.request(state['agents'][aid]['model'], 'communicate', system,
                views[aid], request_key=f'communicate:{state["round"]}:{turn + 1}:{aid}')
            charge=response_size(cfg,response)
            if not isinstance(response, dict) or set(response) != {'communication'} or not isinstance(response['communication'], dict):
                # A returned malformed decision consumes a turn and is audited;
                # transport failures still interrupt for durable recovery.
                response={'communication':{'op':'invalid','raw_response':response}}
            with society.lock:
                decisions[aid] = response
                charges[aid] = charge
                persist()
        with ThreadPoolExecutor(max_workers=max(1, min(cfg.get('parallel_agents', 1), len(members)))) as pool:
            futures = [pool.submit(decide, aid) for aid in members]
            errors = []
            for f in futures:
                try: f.result()
                except Exception as exc: errors.append(exc)
            if errors:
                raise errors[0]
        # The preceding journal holds the complete pre-resolution state. Resolve
        # deterministically, then commit the whole microturn; replay never repeats a paid response.
        for aid in members:
            state['agents'][aid]['inbox'] = []
        order = sorted(members)
        random.Random(f'{cfg["seed"]}:{state["round"]}:dialogue:{turn}').shuffle(order)
        for aid in order:
            msg = decisions[aid]['communication']
            before=used.get(aid,0)
            used[aid]=before+charges[aid]
            outcome = {}
            extra = max(0, charges[aid] - max(0, limits[aid] + shared_used.get(aid, 0) - before))
            if cfg['world'].get('mechanism') == 'mini_world' and unit != 'communication_turns' and extra:
                import functional_effects
                chat = msg.get('chat')
                eligible = [key for key, c in state['chats'].items() if c['open'] and aid in c['members']]
                if chat not in eligible: chat = eligible[0] if eligible else None
                paid = functional_effects.spend_shared(state, aid, extra, chat)
                shared_used[aid] = shared_used.get(aid, 0) + paid
                outcome['shared_budget_charge'] = paid
                outcome['shared_budget_chat'] = chat
            try:
                if before >= limits[aid] + shared_used.get(aid, 0) - outcome.get('shared_budget_charge', 0) and msg.get('op') not in ('send', 'silent', 'leave', 'close'):
                    raise ValueError('Shared conversation extension requires a conversation operation')
                recipients = _valid_message(society, aid, msg, views[aid])
                if msg.get('op') == 'send': outcome['private_recipients'] = recipients
            except (ValueError, TypeError, KeyError) as exc:
                from interface_feedback import record_error
                record_error(outcome,'communication',exc)
            if msg.get('op') == 'silent':
                stopped.append(aid)
            record = {'round': state['round'], 'dialogue_turn': turn + 1, 'agent': aid,
                'communication': copy.deepcopy(msg), 'outcome': outcome,
                'observed_messages': copy.deepcopy(views[aid]['new_messages'])}
            record.update(budget_unit=unit,budget_charge=charges[aid],budget_used_before=before,
                          budget_used_after=used[aid],budget_limit=effective_limits[aid],budget_overrun=max(0,used[aid]-effective_limits[aid]),
                          end_reason='voluntary' if msg.get('op')=='silent' else 'budget' if used[aid]>=effective_limits[aid] else None)
            state['communication_events'].append(record)
            trace.setdefault(aid, []).append(copy.deepcopy(record))
        progress['dialogue_turn'] = turn + 1
        progress['dialogue_decisions'] = {}
        progress['dialogue_charges'] = {}
        progress['dialogue_visible'] = {}
        persist()
    progress['phase'] = 'decide'
    persist()
