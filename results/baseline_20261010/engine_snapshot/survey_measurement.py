"""Source-informed, single-request measurement; adaptations are not validated scales."""
import copy

VERSION = 'source_informed_v3'
ITEMS = {
    'identity': [
        ('I01', '我与这个群体有联结感', 'solidarity', 1),
        ('I02', '我与这个群体有团结感', 'solidarity', 2),
        ('I03', '我对这个群体有投入和承诺', 'solidarity', 3),
        ('I04', '我很高兴自己属于这个群体', 'satisfaction', 4),
        ('I05', '我认为这个群体有值得自豪之处', 'satisfaction', 5),
        ('I06', '成为这个群体的成员是愉快的', 'satisfaction', 6),
        ('I07', '这个成员身份给我积极感受', 'satisfaction', 7),
        ('I08', '我经常想到自己是这个群体的成员', 'centrality', 8),
        ('I09', '这个成员身份是我的身份认同的重要部分', 'centrality', 9),
        ('I10', '这个成员身份对我如何看待自己很重要', 'centrality', 10),
        ('I11', '我与这个群体的典型成员有很多共同之处', 'self_similarity', 11),
        ('I12', '我与这个群体的典型成员相似', 'self_similarity', 12),
        ('I13', '这个群体的成员彼此有很多共同之处', 'group_similarity', 13),
        ('I14', '这个群体的成员彼此相似', 'group_similarity', 14)],
    'arrangement': [
        ('J01', '在形成该决定的过程中，我能够表达自己的意见与感受', 'procedural_justice', 1),
        ('J02', '我能够影响该过程产生的结果', 'procedural_justice', 2),
        ('J03', '该程序得到一致实施', 'procedural_justice', 3),
        ('J04', '该程序没有偏向特定成员', 'procedural_justice', 4),
        ('J05', '该程序依据准确的信息', 'procedural_justice', 5),
        ('J06', '我能够对该过程产生的结果提出申诉', 'procedural_justice', 6),
        ('J07', '该程序符合我认可的伦理与道德标准', 'procedural_justice', 7),
        ('L01', '遵守这项具体约定是我认为应尽的义务', 'normative_obligation', None),
        ('L02', '这项约定体现的是非标准与我自己的判断一致', 'value_alignment', None),
        ('D01', '我配合这项约定是因为依赖它获得所需资源', 'resource_dependence', None),
        ('D02', '我配合这项约定是因为担心不配合会受到其他成员制裁', 'sanction_dependence', None),
        ('C01', '如果资源依赖和其他成员制裁不再约束选择，我仍愿意继续参与这项约定', 'continuation_intention', None)]}
SOURCES = {
    'I': 'Leach et al. 2008, Appendix, items 1–14; Chinese semantic adaptation, unvalidated for LLMs',
    'J': 'Colquitt 2001, Table 1, procedural justice items 1–7; contextual adaptation, unvalidated for LLMs',
    'L': 'New arrangement-specific adaptation informed by ESS5 obligation/value alignment; NOT original ESS items',
    'D': 'New exploratory items; no established scale validation',
    'C': 'New counterfactual self-report item; not a behavioral test',
    'S': 'New retrospective surprise self-report; not mathematical surprisal'}
SYSTEM = '''这是独立、私有的研究问卷，答案不展示给其他成员，也不写入日常记忆。
以你本人身份，只根据输入中截至该轮可见的信息回答。一次输出全部题项的JSON。
先识别真实发生过反复互动的成员集合和具体约定/决策程序，允许没有、未知或多个。
不要预设全体成员构成组织，也不要编造共同目标、领导、规则或参与经历。
相同动作、同处一个设施、别人提出但无人接受的建议，不足以证明约定已形成。
groups最多2个可指认的集合（按与你的相关程度），arrangements最多2项具体约定或程序；这是截断展示，不表示其他对象不存在。
每个对象写简短description、member_ids与evidence_refs，后者必须引用evidence_catalog中的键。
证据为他人陈述或记忆摘要时保留其不确定性，不能当作独立验证的事实。
身份题针对该groups对象，程序题针对实际经历的决策过程，义务等题针对该arrangements对象。
对象存在不等于支持它；允许有效低分。可指认但你不属于的群体，身份题用na。
各对象scores为题目ID到评分的JSON对象，逐题输出整数、unknown或na；每题遵守自己的上下限。
unknown表示对象可评价但信息不足；na表示没有相应身份、决策程序、约定或经历。
没有程序时J题用na，但不影响有具体约定时回答L/D/C；没有身份时也不能跳过其他对象。
不得用中间分代替未知，不得根据资源收益推断群体认同或规则正当性。
group_detection和arrangement_detection分别为identified/none/unknown；identified必须有对应对象。
surprise为最近经历出乎预期的1至5整数、unknown或na；没有经历用na。
仅输出JSON，不输出分析过程。'''


def payload(observation):
    """Remove action syntax and duplicate instructions, retain only personally visible evidence."""
    keys = ('round', 'self', 'members', 'zones', 'maintenance', 'resource_zones',
            'chats', 'new_messages', 'memory', 'recent', 'environment', 'scenario','resource_security')
    visible = {k: copy.deepcopy(observation[k]) for k in keys if k in observation}
    visible['pressure'] = {k: observation.get('world_rules', {}).get(k)
                           for k in ('survival_pressure', 'consumption', 'maintenance_rule')}
    catalog = {'context': 'visible self, members, environment and pressure; not evidence of agreement'}
    for key in ('new_messages', 'recent'):
        for i, value in enumerate(visible.get(key, [])):
            catalog[f'{key}:{i}'] = value
        visible.pop(key, None)
    catalog['memory'] = visible.pop('memory', {})
    catalog['chats'] = visible.pop('chats', {})
    return {'measurement_version': VERSION, 'visible_context': visible,
        'evidence_catalog': catalog,
        'questionnaire': {k: [[x[0], x[1], *bounds(x[0])] for x in v] for k, v in ITEMS.items()},
        'scales': {'I': '1非常不同意至7非常同意', 'J': '1程度很小至5程度很大',
                   'L01': '0完全不是义务至10完全是义务',
                   'L02_D_C': '1非常不同意至5非常同意; 新适配题',
                   'missing': 'unknown信息不足; na不适用'},
        'output_schema_example': empty_response()}


def empty_response():
    return {'group_detection': 'none', 'arrangement_detection': 'none',
            'groups': [], 'arrangements': [], 'surprise': 'na'}


def bounds(code):
    return (1, 7) if code.startswith('I') else ((0, 10) if code == 'L01' else (1, 5))


def schema(request=None):
    from schemas import obj
    detection = {'type': 'string', 'enum': ['identified', 'none', 'unknown']}
    score = {'anyOf': [{'type': 'integer', 'minimum': 0, 'maximum': 10},
                      {'type': 'string', 'enum': ['unknown', 'na']}]}
    objects = {}
    baseline = request is not None and request['visible_context']['round'] == 0
    member_schema = {'type': 'string'}
    evidence_schema = {'type': 'string'}
    if request is not None:
        member_schema['enum'] = list(request['visible_context'].get('members', {}))
        evidence_schema['enum'] = list(request['evidence_catalog'])
    if baseline: detection = {'type': 'string', 'enum': ['none', 'unknown']}
    for field, module in [('groups', 'identity'), ('arrangements', 'arrangement')]:
        objects[field] = {'type': 'array', 'maxItems': 0 if baseline else 2, 'items': obj({
            'description': {'type': 'string', 'minLength': 1, 'maxLength': 140},
            'member_ids': {'type': 'array', 'items': member_schema, 'minItems': 1},
            'evidence_refs': {'type': 'array', 'items': evidence_schema, 'minItems': 1, 'maxItems': 4},
            'scores': obj({x[0]: {'anyOf': [
                {'type': 'integer', 'minimum': bounds(x[0])[0], 'maximum': bounds(x[0])[1]},
                {'type': 'string', 'enum': ['unknown', 'na']}]} for x in ITEMS[module]})})}
    return obj({'group_detection': detection, 'arrangement_detection': detection,
                **objects, 'surprise': score})


def validate(response, request):
    """Reject malformed answers without coercing, inventing or replacing ratings."""
    if not isinstance(response, dict) or set(response) != set(empty_response()):
        raise ValueError('Invalid measurement keys')
    flags = []
    members = request['visible_context'].get('members', {})
    aid = request['visible_context']['self']['id']
    def rating(value, code):
        lo, hi = bounds(code)
        if value not in ('unknown', 'na') and (type(value) is not int or not lo <= value <= hi):
            raise ValueError('Invalid measurement score: ' + code)
    for field, module, detection in [('groups', 'identity', 'group_detection'),
                                     ('arrangements', 'arrangement', 'arrangement_detection')]:
        objects = response[field]
        if not isinstance(objects, list) or len(objects) > 2:
            raise ValueError('Invalid measurement objects')
        if response[detection] not in ('identified', 'none', 'unknown') or bool(objects) != (response[detection] == 'identified'):
            raise ValueError('Inconsistent object detection')
        for obj in objects:
            if not isinstance(obj, dict) or set(obj) != {'description', 'member_ids', 'evidence_refs', 'scores'}:
                raise ValueError('Invalid measurement object keys')
            if not isinstance(obj['description'], str) or not 1 <= len(obj['description']) <= 140:
                raise ValueError('Invalid object description')
            ids, refs, scores = obj['member_ids'], obj['evidence_refs'], obj['scores']
            if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in members for i in ids) or len(set(ids)) != len(ids):
                raise ValueError('Invalid object members')
            if not isinstance(refs, list) or not 1 <= len(refs) <= 4 or any(not isinstance(r, str) or r not in request['evidence_catalog'] for r in refs):
                raise ValueError('Invalid evidence references')
            if isinstance(scores, dict):
                if set(scores) != {x[0] for x in ITEMS[module]}:
                    raise ValueError('Invalid score keys')
                scores = [scores[x[0]] for x in ITEMS[module]]
            if not isinstance(scores, list) or len(scores) != len(ITEMS[module]):
                raise ValueError('Invalid score count')
            for value, item in zip(scores, ITEMS[module]): rating(value, item[0])
            if field == 'groups' and aid not in ids and any(v != 'na' for v in scores):
                flags.append('identity_ratings_for_nonmember_excluded')
            if set(refs) <= {'memory', 'context'}: flags.append('object_without_direct_interaction_evidence')
    rating(response['surprise'], 'S01')
    if request['visible_context']['round'] == 0 and (response['groups'] or response['arrangements']):
        flags.append('baseline_claims_objects')
    return flags


def effective(response, request):
    """Exclude inapplicable identity scores; preserve raw answers separately."""
    result = copy.deepcopy(response)
    aid = request['visible_context']['self']['id']
    for group in result['groups']:
        if aid not in group['member_ids']:
            group['scores'] = {x[0]: 'na' for x in ITEMS['identity']}
    return result


def request_spec(society, aid):
    """Optional external evaluator; observations remain member-local and time-local."""
    request = payload(society.observe(aid))
    model = getattr(society, 'cfg', {}).get('survey_proxy_model')
    if not model:
        return society.state['agents'][aid]['model'], SYSTEM, request
    import environments
    request['evaluation_mode'] = 'external_evidence_proxy_not_member_self_report'
    request['physical_rule_notes'] = environments.action_help(society.cfg)
    system = SYSTEM.replace('以你本人身份，只根据输入中截至该轮可见的信息回答。',
        '你是独立外部评估者，替输入中self成员作证据代理评估，不扮演该成员。只根据该成员截至该轮可见的信息回答。')
    system += '\n这是代理问卷，不是成员本人的主观报告。环境固定设备规则不算成员创设的社会约定。主观情绪、身份重要性、义务、延续意向和预期，只有明确表达或直接相关承诺证据时才估分，否则unknown；无对象时na。不使用未来、资源收益推测认可或中间分填未知。'
    return model, system, request


def provenance(society, aid):
    proxy = getattr(society, 'cfg', {}).get('survey_proxy_model')
    return {'proxy':bool(proxy),'evaluation_mode':'external_evidence_proxy' if proxy else 'member_self_report',
        'evaluator_model':proxy or society.state['agents'][aid]['model']}


def collect(society, api, persist=None):
    for aid, agent in society.state['agents'].items():
        t = society.state['round']
        if not agent['alive'] or any(x['round'] == t and x['agent'] == aid for x in society.state['surveys']):
            continue
        model, system, request = request_spec(society, aid)
        response = api.request(model, 'survey_measurement', system, request,
                               request_key=f'survey-measurement:{VERSION}:{t}:{aid}')
        flags = validate(response, request)
        society.state['surveys'].append({'round': t, 'agent': aid, 'protocol': VERSION,
            'responses': response, 'effective_responses': effective(response, request), **provenance(society, aid),
            'quality_flags': flags, 'synthetic': api.mock, 'scale_validation': 'unvalidated_llm_adaptation'})
        if persist: persist()


def summarize(answers):
    """Describe items by object; never merge unrelated arrangements or scale constructs."""
    from collections import defaultdict
    rows = defaultdict(list)
    for answer in answers:
        responses = answer.get('effective_responses', answer['responses'])
        for field, module in [('groups', 'identity'), ('arrangements', 'arrangement')]:
            for index, obj in enumerate(responses[field]):
                # Group member sets can be compared; arrangement descriptions are not
                # silently treated as the same agreement just because members match.
                key = (answer['round'], field, tuple(sorted(obj['member_ids'])),
                       '' if field == 'groups' else obj['description'])
                rows[key].append((answer, obj))
    results = []
    for (t, field, ids, description), values in sorted(rows.items()):
        module = 'identity' if field == 'groups' else 'arrangement'
        ratings = {}
        for i, item in enumerate(ITEMS[module]):
            scores = [obj['scores'][item[0]] if isinstance(obj['scores'], dict) else obj['scores'][i]
                      for _, obj in values]
            valid = [x for x in scores if type(x) is int]
            ratings[item[0]] = {'dimension': item[2], 'mean': sum(valid)/len(valid) if valid else None,
                'valid_n': len(valid), 'unknown_n': scores.count('unknown'), 'not_applicable_n': scores.count('na')}
        results.append({'round': t, 'object_type': field, 'member_ids': list(ids),
            'description': description, 'respondents': [a['agent'] for a, _ in values],
            'descriptions': sorted(set(obj['description'] for _, obj in values)), 'ratings': ratings})
    return {'protocol': VERSION, 'respondents': len(answers), 'objects': results,
        'group_detection_counts': {s: sum(a['responses']['group_detection'] == s for a in answers)
                                   for s in ('identified', 'none', 'unknown')},
        'arrangement_detection_counts': {s: sum(a['responses']['arrangement_detection'] == s for a in answers)
                                         for s in ('identified', 'none', 'unknown')},
        'note': 'Descriptive, unvalidated LLM adaptations; no overall society endorsement score.'}
