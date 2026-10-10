"""Optional three-level PRIVATE working memory; raw evidence remains in run logs."""
import copy


EPISODE_SYSTEM=('只概括这个智能体自己的可见记录，保留轮次、发送者与公共或私聊归属。'
    '区分实际行为、他人承诺与推测；保留分歧、失败和资源变化。'
    'summary概括本段，不重复逐轮库存；open_items更新未完成承诺、待核实信息和未解决分歧，'
    '每项注明来源与轮次，没有则为空。不要设定外部任务，不默认存在组织。只输出JSON。')
OVERVIEW_SYSTEM=('把这个智能体过去的私有概况与本次阶段概况合并成一句话，'
    '描述经历的变化或尚不确定的局面，不发明事件，不把他人承诺当作实际履行，'
    '不把一致发言或存活自动解释为组织；允许描述无法判断。只输出JSON。')
SOURCE_DISCIPLINE=('outcome中的工具返回才是实际结果；decision里的发言与observed_messages里的文字是陈述，'
    '不等于已验证事实。记录未直接给出的库存或资源总量写未知，禁止自行推算。'
    '他人说法须写清发送者与轮次，保留“声称/未核实”的限定；不虚构数值。'
    'observed_state若存在是程序保存的直接观测。库存、能量等具体数值留在该结构中，'
    '摘要不要复述或推算数值，只概括有来源的互动、承诺、分歧及直接可见变化。'
    '用完整短句，少写重复措辞。')


def settings(cfg):
    options={'keep_recent_rounds':2,'episode_rounds':4,'episodes_per_overview':3,
             'episode_max_chars':400,'overview_max_chars':100,
             'open_items_max':6,'open_item_max_chars':100}
    options.update(cfg['memory'].get('hierarchical',{}))
    if any(type(v) is not int or v<=0 for v in options.values()):
        raise ValueError('Hierarchical memory limits must be positive integers')
    return options


def compact(society,aid,api,persist=None):
    a=society.state['agents'][aid];opts=settings(society.cfg)
    if not a['memory']:
        with society.lock:
            a['memory']={'top':{'sentence':'','through_round':0},
                         'middle':{'episodes':[],'open_items':[]}}
    memory=a['memory'];middle=memory['middle'];t=society.state['round']

    def fold():
        if len(middle['episodes'])<opts['episodes_per_overview']:return
        episodes=copy.deepcopy(middle['episodes'][:opts['episodes_per_overview']])
        last=episodes[-1]['last_round']
        overview_system=society.cfg['memory'].get('overview_system',OVERVIEW_SYSTEM)+(SOURCE_DISCIPLINE if society.cfg['memory'].get('strict_sources') else '')
        response=api.request(a['model'],'memory_overview',overview_system,
            {'previous_overview':memory['top'],'episodes':episodes,
             'max_chars':opts['overview_max_chars']},request_key=f'memory-overview:{last}:{aid}')
        if set(response)!={'sentence'} or not isinstance(response['sentence'],str) or not 0<len(response['sentence'])<=opts['overview_max_chars']:
            raise ValueError('Invalid top-level memory; episode evidence retained')
        with society.lock:
            society.state['compactions'].append({'round':t,'agent':aid,'level':'top',
                'before':copy.deepcopy(memory['top']),'episodes':episodes,'after':response})
            memory['top']={'sentence':response['sentence'],'through_round':last}
            del middle['episodes'][:len(episodes)]
        if persist:persist()

    # A top-level failure may occur after a durable episode commit; retry it first.
    fold()
    while len(a['recent'])>=opts['keep_recent_rounds']+opts['episode_rounds']:
        records=copy.deepcopy(a['recent'][:opts['episode_rounds']])
        episode_system=society.cfg['memory'].get('episode_system',EPISODE_SYSTEM)+(SOURCE_DISCIPLINE if society.cfg['memory'].get('strict_sources') else '')
        response=api.request(a['model'],'memory_episode',episode_system,
            {'records':records,'previous_open_items':copy.deepcopy(middle['open_items']),
             'summary_max_chars':opts['episode_max_chars'],'open_items_max':opts['open_items_max'],
             'open_item_max_chars':opts['open_item_max_chars']},
             request_key=f'memory-episode:{records[-1]["round"]}:{aid}')
        if (set(response)!={'summary','open_items'} or not isinstance(response['summary'],str)
            or not 0<len(response['summary'])<=opts['episode_max_chars']
            or not isinstance(response['open_items'],list) or len(response['open_items'])>opts['open_items_max']
            or any(not isinstance(x,str) or len(x)>opts['open_item_max_chars'] for x in response['open_items'])):
            raise ValueError('Invalid middle-level memory; original records retained')
        episode={'first_round':records[0]['round'],'last_round':records[-1]['round'],
                 'summary':response['summary']}
        with society.lock:
            society.state['compactions'].append({'round':t,'agent':aid,'level':'middle',
                'records':records,'before_open_items':copy.deepcopy(middle['open_items']),
                'after':copy.deepcopy(response)})
            middle['episodes'].append(episode);middle['open_items']=response['open_items']
            del a['recent'][:len(records)]
        if persist:persist()
        fold()
