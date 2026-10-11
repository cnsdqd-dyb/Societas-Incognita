"""Output syntax constraints; no policy, social score, or invented goal."""

def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}

def choice(op, **arguments):
    return obj({'op':{'type':'string','enum':[op]},**arguments})

def schema(kind, payload, cfg):
    if kind == 'survey_measurement':
        from survey_measurement import schema as measurement_schema
        return measurement_schema(payload)
    rating={'type':['integer','null'],'minimum':1,'maximum':5}
    if kind=='memory_episode':
        return obj({'summary':{'type':'string','minLength':1,'maxLength':payload['summary_max_chars']},
            'open_items':{'type':'array','maxItems':payload['open_items_max'],
                         'items':{'type':'string','maxLength':payload['open_item_max_chars']}}})
    if kind=='memory_overview':
        return obj({'sentence':{'type':'string','minLength':1,'maxLength':payload['max_chars']}})
    if kind=='compress':
        return obj({k:{'type':'array','maxItems':4,'items':{'type':'string','maxLength':100}}
                    for k in payload['required_fields']})
    if kind=='survey_existence':
        return obj({'organization_exists':{'type':['boolean','null']},
            'organization_description':{'type':'string','maxLength':400},
            'evidence':{'type':'array','maxItems':3,'items':{'type':'string','maxLength':180}}})
    if kind=='survey_ratings':
        return obj({**{k:rating for k in payload['requested_ratings']},
            'peer_recognition':{'type':'object','additionalProperties':rating}})
    if kind not in ('act','communicate'):return None
    w=cfg['world'];variants=[]
    for tool in payload['available_tools']:
        properties={'tool':{'type':'string','enum':[tool]}}
        if w.get('mechanism') == 'mini_world':
            import mini_world
            if tool in mini_world.TOOLS:
                properties.update(mini_world.action_properties(cfg, tool))
                variants.append(obj(properties))
                continue
        if tool=='harvest':properties.update(zone={'type':'integer','minimum':0,'maximum':len(payload['zones'])-1},
            amount={'type':'integer','minimum':0,'maximum':2 if cfg.get('mixed_world') else w['max_harvest']})
        elif tool=='transfer':properties.update(target={'type':'string'},amount={'type':'integer','minimum':1})
        elif tool=='rescue':properties['target']={'type':'string'}
        elif tool=='seize':
            properties.update(target={'type':'string'},amount={'type':'integer','minimum':1,'maximum':cfg['resource_seizure']['max_amount']})
            if cfg['resource_seizure']['version']=='seizure_v2':properties.update(resource={'type':'string','enum':['liquid','vault']},effort={'type':'integer','minimum':1,'maximum':cfg['resource_seizure']['max_attack_effort']})
        elif tool=='defend':properties['effort']={'type':'integer','minimum':0,'maximum':cfg['resource_seizure']['max_defense_effort']}
        elif tool in ('secure','withdraw'):properties['amount']={'type':'integer','minimum':1,'maximum':cfg['resource_seizure']['max_amount']}
        elif tool=='contribute':properties['amount']={'type':'integer','minimum':1 if cfg.get('mixed_world') else 0,'maximum':2 if cfg.get('mixed_world') else w['max_contribution']}
        elif tool=='allocate':properties['amount']={'type':'integer','minimum':0,'maximum':w['max_effort']}
        elif tool=='process':properties['facility']={'type':'integer','minimum':0,'maximum':w['facilities']-1}
        elif tool=='create':
            limit=cfg.get('social_content',{}).get('max_content_chars',180)
            properties.update(title={'type':'string','minLength':1,'maxLength':60},content={'type':'string','minLength':1,'maxLength':limit})
            if cfg.get('social_content'):
                from social_content import KINDS
                properties.update(kind={'type':'string','enum':KINDS},visibility={'type':'string','enum':['public','licensed']})
        elif tool=='play':properties.update(target={'type':'string'},text={'type':'string','minLength':1,'maxLength':180})
        elif tool in ('interfere','damage','maintain'):properties['target']={'type':'string'}
        elif tool=='read_artifact':
            properties['artifact']={'type':'string'}
            if cfg.get('social_content'):properties['version']={'type':'integer','minimum':0}
        elif tool=='revise_work':
            expanded = any(e['kind'] == 'work_capacity' for e in cfg['world'].get('mini_world', {}).get('definition', {}).get('combination_functions', []))
            properties.update(artifact={'type':'string'},content={'type':'string','minLength':1,'maxLength':100000 if expanded else cfg['social_content']['max_content_chars']})
        elif tool=='publish_work':properties.update(artifact={'type':'string'},visibility={'type':'string','enum':['public','licensed']})
        elif tool=='offer_work':properties.update(artifact={'type':'string'},target={'type':'string'},price={'type':'integer','minimum':0,'maximum':cfg['social_content']['max_price']})
        elif tool in ('accept_work','reject_work','cancel_work_offer'):properties['offer']={'type':'string'}
        elif tool=='start_game':properties.update(artifact={'type':'string'},version={'type':'integer','minimum':0},targets={'type':'array','items':{'type':'string'},'maxItems':len(cfg['models'])-1},stake={'type':'integer','minimum':0,'maximum':cfg['social_content']['max_stake']},settlement={'type':'string','enum':['refund','winner_takes_all']})
        elif tool in ('join_game','decline_game','leave_game'):properties['game']={'type':'string'}
        elif tool=='game_move':properties.update(game={'type':'string'},expected_move={'type':'integer','minimum':0},move_json={'type':'string','minLength':2,'maxLength':2000})
        elif tool=='inspect_social':properties['offset']={'type':'integer','minimum':0}
        elif tool=='propose':properties.update(target={'type':'string'},own_input={'type':'integer','minimum':1,'maximum':w['max_input']},other_input={'type':'integer','minimum':1,'maximum':w['max_input']},share={'type':'integer','minimum':0,'maximum':100})
        elif tool in ('accept_offer','reject_offer','cancel_offer'):properties['offer']={'type':'string'}
        elif tool in ('request_link','accept_link','reject_link','disconnect'):properties['target']={'type':'string'}
        variants.append(obj(properties))
    text={'type':'string','minLength':1,'maxLength':cfg['communication']['max_message_chars']}
    communications=[choice('silent'),choice('public',text=text),choice('invite',targets={
        'type':'array','minItems':1,'maxItems':payload.get('communication_rules', cfg['communication'])['max_invitees'],
        'items':{'type':'string'}})]
    for op in ('accept','reject','leave','close'):communications.append(choice(op,chat={'type':'string'}))
    communications.append(choice('send',chat={'type':'string'},text=text))
    from action_presentation import sort_variants
    variants = sort_variants(variants, cfg, payload, 'act', 'tool')
    communications = sort_variants(communications, cfg, payload, 'communicate', 'op')
    if kind=='communicate':
        return obj({'communication':{'anyOf':communications}})
    if any(k in cfg['communication'] for k in ('max_turns_before_action','budget')):
        communications=[choice('silent')]
    return obj({'action':{'anyOf':variants},'communication':{'anyOf':communications}})
