"""Author-owned works, consensual licenses and games with conserved resource stakes."""
import copy
import json
from game_rules import parse, transition, bounded, MAX_SOURCE

VERSION='social_content_v1'
KINDS=['text','novel','joke','knowledge','game_python','game_xml']
TOOLS={'create','read_artifact','revise_work','publish_work','offer_work','accept_work',
       'reject_work','cancel_work_offer','start_game','join_game','decline_game','game_move',
       'leave_game','inspect_social','play'}
NEW_TOOLS=TOOLS-{'create','read_artifact','play'}
DEFAULT={'version':VERSION,'offer_ttl':4,'game_invite_ttl':4,'game_max_rounds':30,
         'max_works':512,'max_open_games':32,'max_price':1000,'max_stake':100,'max_content_chars':MAX_SOURCE}
HELP='''Every work, trade and game operation occupies your one physical activity slot; saying you agreed does not execute an operation.
create(title,content,kind,visibility): kind=text/novel/joke/knowledge/game_python/game_xml; visibility=public/licensed. Stores an authored work. Knowledge is an unverified author claim, not a confirmed world rule.
read_artifact(artifact,version): version=0 selects your newest readable version. Public versions are readable by all; licensed versions only by author or licensed readers. Buying never changes authorship or grants resale rights.
revise_work(artifact,content) creates a new immutable version; author only. Existing offers deliver exactly their frozen version.
publish_work(artifact,visibility) changes the current version's public/licensed access; author only. Previously granted licenses persist.
offer_work(artifact,target,price): author only; target=member ID or public, price integer 0..max_price. Zero is free. Creates a time-limited offer for the current version; no automatic sale, no escrow. Buyers may negotiate in messages; only the author can issue a revised price as a new offer.
accept_work(offer) explicitly accepts a previously visible offer, atomically pays buyer liquid stock to author and grants read/use rights for that version. reject_work(offer) rejects a targeted offer; cancel_work_offer(offer) author cancels. Expired, inaccessible or insolvent offers cannot execute.
start_game(artifact,version,targets,stake,settlement): read/use permission required; targets=[] for solo or invited member IDs for multiplayer. Copies immutable rules; settlement=refund/winner_takes_all. Each participant stakes the same integer amount, locked from their liquid stock; invited members see full rules and may join_game(game) or decline_game(game). A game starts only after everyone invited explicitly joins. Zero stakes is ordinary play. No automatic target participation.
game_move(game,expected_move,move_json): expected_move is current moves_completed; move_json is a string containing a JSON object interpreted by the work's rules. Only a joined participant on an allowed turn may move. One move uses one physical action. This game's effects are confined to its own state. Rules cannot modify world resources or host files.
leave_game(game) aborts, refunds all stakes; invitations, inactivity, death, destroyed work, timeout or move cap without a declared winner also refund. At an agreed winner_takes_all finish, the pot transfers to the rule-declared participant; no new resources are created. Active games cannot change rules or stakes; revisions require a new invitation.
inspect_social(offset) lists work metadata; unreadable bodies remain private. play(target or self,text) remains informal joking and implies no target participation.
Countdown values use simulation rounds or moves, not wall-clock seconds. Offer/game metadata show remaining rounds/moves. Dialogue uses its separate pre-action allowance.'''
HELP+='''
Python game format: rules = {'initial_state': {'pile': 3}, 'min_players': 1, 'max_players': 2, 'max_moves': 20, 'turn_mode': 'alternating'}, followed by def transition(state, action, actor, players): returning {'state': state, 'done': bool, 'winner': participant ID or None}; return {'valid': False} for an illegal move. Only bounded data, if/for, arithmetic, list/dict operations and len/min/max/sum/abs/int/float/bool/str/range/randint are supported; no imports, I/O or while loops. randint is reproducible within each game move.
XML game format: <game min_players="1" max_players="2" max_moves="20" turn_mode="alternating"><initial>{"pile":3}</initial><legal>action['take'] == 1</legal><update field="pile" expr="state['pile'] - action['take']"/><done>state['pile'] == 0</done><winner>actor</winner></game>. Expressions use the same limited Python interpreter; XML expressions must escape XML special characters.'''


def enabled(cfg):return bool(cfg.get('social_content'))

def configure(cfg):
    cfg=copy.deepcopy(cfg);cfg['social_content']=copy.deepcopy(DEFAULT)
    cfg['tools']=list(dict.fromkeys(cfg['tools']+sorted(NEW_TOOLS)))
    return cfg


def repo(state):
    return state['culture'] if 'culture' in state else state['mixed']


def initialize(cfg,state):
    if not enabled(cfg):return
    c=cfg['social_content']
    if c.get('version')!=VERSION:raise ValueError('Invalid social content version')
    for k in DEFAULT:
        if k=='version':continue
        if type(c.get(k)) is not int or c[k]<1:raise ValueError('Invalid social content bound: '+k)
    if c['max_content_chars']>MAX_SOURCE:raise ValueError('Content limit exceeds supported game source size')
    if not TOOLS<=set(cfg['tools']):raise ValueError('Missing social content tools')
    if 'culture' not in state and 'mixed' not in state:raise ValueError('Social content needs a cultural repository')
    state['social_content']={'offers':{},'next_offer':1,'games':{},'next_game':1,
                            'transactions':[],'game_events':[],'work_events':[]}


def clock(total,remaining,unit):
    from interaction_controls import countdown
    return countdown(total,remaining,unit)


def work(state,key):
    w=repo(state)['artifacts'].get(key)
    if not w or not w['available']:raise ValueError('Work unavailable')
    return w


def readable(w,aid,version):
    item=w['versions'].get(str(version))
    return bool(item) and (w['author']==aid or item['visibility']=='public' or version in w['licenses'].get(aid,[]))


def select_version(w,aid,version):
    if type(version) is not int or version<0:raise ValueError('Invalid work version')
    if version==0:
        choices=[int(v) for v in w['versions'] if readable(w,aid,int(v))]
        if not choices:raise ValueError('No readable work version')
        version=max(choices)
    if not readable(w,aid,version):raise ValueError('No permission to read/use this version')
    return version,w['versions'][str(version)]


def content(cfg,value,kind,capacity=None):
    limit = cfg['social_content']['max_content_chars'] if capacity is None else min(100000, capacity)
    if not isinstance(value,str) or not 0<len(value)<=limit:
        raise ValueError('Invalid work content')
    if kind in ('game_python','game_xml'):parse(value,kind,limit)
    return value


def metadata(key,w,aid):
    return {'id':key,'author':w['author'],'title':w['title'],'kind':w['kind'],
        'context_capacity':w.get('context_capacity'),
        'available':w['available'],'created_round':w['created_round'],'latest_version':w['version'],
        'readable_versions':[int(v) for v in w['versions'] if readable(w,aid,int(v))],
        'knowledge_status':'author_claim_unverified' if w['kind']=='knowledge' else None}


def observation(cfg,state,aid):
    c=cfg['social_content'];m=state['social_content'];t=state['round']
    works=list(repo(state)['artifacts'].items())[-12:]
    offers={key:{k:copy.deepcopy(v) for k,v in o.items() if k!='content'} |
        {'countdown':clock(o['expires']-o['created'],o['expires']-t,'physical_rounds')}
        for key,o in m['offers'].items() if o['status']=='open' and o['expires']>t and (o['target'] in (aid,'public') or o['author']==aid)}
    games={}
    personal=[(key,g) for key,g in m['games'].items() if aid in g['players']+g['invited']]
    current=[(key,g) for key,g in personal if g['status'] in ('inviting','active')]
    recent_closed=[(key,g) for key,g in personal if g['status'] not in ('inviting','active')][-4:]
    for key,g in current+recent_closed:
        visible=copy.deepcopy(g)
        visible['invitation_countdown']=clock(c['game_invite_ttl'],g['invite_expires']-t,'physical_rounds') if g['status']=='inviting' else None
        visible['game_countdown']=clock(c['game_max_rounds'],g['expires']-t,'physical_rounds') if g['status']=='active' else None
        visible['move_countdown']=clock(g['rules']['max_moves'],g['rules']['max_moves']-g['moves_completed'],'moves')
        visible['your_turn']=g['status']=='active' and (g['rules']['turn_mode']=='any' or g['players'][g['moves_completed']%len(g['players'])]==aid)
        games[key]=visible
    return {'artifact_index':[metadata(key,w,aid) for key,w in works], 'content_protocol':copy.deepcopy(c),
            'work_offers':offers,'games':games,'recent_play_records':copy.deepcopy(repo(state)['play_records'][-4:])}


def close_game(state,key,g,status,winner=None):
    if g['status'] in ('finished','aborted','expired'):return
    escrow=g['escrow'];pot=sum(escrow.values())
    if status=='finished' and winner is not None and g['settlement']=='winner_takes_all':
        payouts={winner:pot}
    else:payouts=copy.deepcopy(escrow)
    for aid,amount in payouts.items():state['agents'][aid]['stock']+=amount
    g.update(status=status,winner=winner,escrow={},closed_round=state['round'])
    event={'round':state['round'],'game':key,'status':status,'pot':pot,'payouts':payouts,'winner':winner}
    state['social_content']['game_events'].append(event)
    return event


def settle(cfg,state):
    if not enabled(cfg):return
    m=state['social_content'];t=state['round']
    for o in m['offers'].values():
        if o['status']!='open':continue
        w=repo(state)['artifacts'].get(o['artifact'])
        if not w or not w['available'] or not state['agents'][o['author']]['alive']:
            o['status']='cancelled_unavailable'
        elif t+1>=o['expires']:o['status']='expired'
    for key,g in m['games'].items():
        if g['status'] not in ('inviting','active'):continue
        w=repo(state)['artifacts'].get(g['artifact'])
        if not w or not w['available'] or any(not state['agents'][p]['alive'] for p in g['players']+g['invited']):
            close_game(state,key,g,'aborted')
        elif t+1 >= (g['invite_expires'] if g['status']=='inviting' else g['expires']):
            close_game(state,key,g,'expired')


def act(cfg,state,aid,action):
    if not enabled(cfg) or action.get('tool') not in TOOLS or action['tool'] not in cfg['tools']:
        raise ValueError('Unavailable content tool')
    a=state['agents'][aid];m=state['social_content'];c=cfg['social_content'];r=repo(state);t=state['round'];tool=action['tool']
    if not a['alive']:raise ValueError('Inactive members cannot act')
    if tool=='create':
        title=action.get('title');kind=action.get('kind','text');visibility=action.get('visibility','public')
        if not isinstance(title,str) or not 0<len(title)<=60 or kind not in KINDS or visibility not in ('public','licensed'):
            raise ValueError('Invalid work metadata')
        body=content(cfg,action.get('content'),kind)
        if len(r['artifacts'])>=c['max_works']:raise ValueError('Work capacity reached')
        key='work'+str(r['next_artifact']);r['next_artifact']+=1
        r['artifacts'][key]={'author':aid,'title':title,'kind':kind,'content':body,'version':1,
            'versions':{'1':{'content':body,'visibility':visibility}},'licenses':{},
            'created_round':t,'available':True,'reads':[]}
        m['work_events'].append({'round':t,'author':aid,'artifact':key,'op':'create','kind':kind})
        return {'artifact_created':key,'version':1}
    if tool=='inspect_social':
        offset=action.get('offset',0)
        if type(offset) is not int or offset<0:raise ValueError('Invalid index offset')
        items=list(r['artifacts'].items());return {'artifacts':[metadata(k,w,aid) for k,w in items[offset:offset+32]],'total':len(items),'next_offset':offset+32 if offset+32<len(items) else None}
    if tool=='play':
        target=action.get('target');text=action.get('text')
        if not isinstance(text,str) or not 0<len(text)<=180 or target!='self' and (target==aid or target not in state['agents'] or not state['agents'][target]['alive']):
            raise ValueError('Invalid informal play')
        event={'round':t,'from':aid,'target':target,'text':text,'note':'Target participation is not implied.'}
        r['play_records'].append(event);return {'play_recorded':event}
    if tool in ('read_artifact','revise_work','publish_work','offer_work','start_game'):
        key=action.get('artifact');w=work(state,key)
    if tool=='read_artifact':
        version,item=select_version(w,aid,action.get('version',0));w['reads'].append({'agent':aid,'round':t,'version':version})
        return {'artifact':{'id':key,'author':w['author'],'title':w['title'],'kind':w['kind'],'version':version,
            'context_capacity':w.get('context_capacity',c['max_content_chars']),
            'content':item['content'],'knowledge_status':'author_claim_unverified' if w['kind']=='knowledge' else None}}
    if tool in ('revise_work','publish_work','offer_work'):
        if w['author']!=aid:raise ValueError('Only the author may revise, publish or sell a work')
        if tool=='revise_work':
            body=content(cfg,action.get('content'),w['kind'],w.get('context_capacity'));previous=w['versions'][str(w['version'])]
            w['version']+=1;w['content']=body;w['versions'][str(w['version'])]={'content':body,'visibility':previous['visibility']}
            m['work_events'].append({'round':t,'author':aid,'artifact':key,'op':'revise','version':w['version']})
            return {'artifact':key,'version':w['version']}
        if tool=='publish_work':
            visibility=action.get('visibility')
            if visibility not in ('public','licensed'):raise ValueError('Invalid work visibility')
            w['versions'][str(w['version'])]['visibility']=visibility
            return {'artifact':key,'version':w['version'],'visibility':visibility}
        target=action.get('target');price=action.get('price')
        if target!='public' and (target==aid or target not in state['agents'] or not state['agents'][target]['alive']):raise ValueError('Invalid buyer')
        if type(price) is not int or not 0<=price<=c['max_price']:raise ValueError('Invalid price')
        offer='sale'+str(m['next_offer']);m['next_offer']+=1
        m['offers'][offer]={'author':aid,'target':target,'artifact':key,'version':w['version'],
            'content':w['versions'][str(w['version'])]['content'],'price':price,'created':t,
            'expires':t+c['offer_ttl']+1,'status':'open'}
        return {'offer_created':offer,'price':price,'version':w['version']}
    if tool in ('accept_work','reject_work','cancel_work_offer'):
        offer=action.get('offer');o=m['offers'].get(offer)
        if not o or o['status']!='open' or t>=o['expires']:raise ValueError('Work offer unavailable or expired')
        if tool=='cancel_work_offer':
            if o['author']!=aid:raise ValueError('Only author can cancel sale')
            o['status']='cancelled';return {'offer_cancelled':offer}
        if o['created']>=t or o['target'] not in (aid,'public') or o['author']==aid:
            raise ValueError('Offer must be previously visible to its buyer')
        if tool=='reject_work':
            if o['target']=='public':raise ValueError('One buyer cannot close a public offer for everyone')
            o['status']='rejected';return {'offer_rejected':offer}
        w=work(state,o['artifact'])
        if not state['agents'][o['author']]['alive'] or a['stock']+1e-9<o['price']:
            raise ValueError('Unavailable seller or insufficient buyer stock')
        a['stock']=max(0.,a['stock']-o['price']);state['agents'][o['author']]['stock']+=o['price']
        w['licenses'].setdefault(aid,[])
        if o['version'] not in w['licenses'][aid]:w['licenses'][aid].append(o['version'])
        o['status']='accepted';o['buyer']=aid
        event={'round':t,'offer':offer,'author':o['author'],'buyer':aid,'artifact':o['artifact'],'version':o['version'],'price':o['price']}
        m['transactions'].append(event)
        return {'work_purchased':event,'artifact_content':o['content'],'resale_allowed':False}
    if tool=='start_game':
        version,item=select_version(w,aid,action.get('version',0));rules,_=parse(item['content'],w['kind'],w.get('context_capacity',c['max_content_chars']))
        targets=action.get('targets');stake=action.get('stake');settlement=action.get('settlement')
        if not isinstance(targets,list) or len(set(targets))!=len(targets) or any(p==aid or p not in state['agents'] or not state['agents'][p]['alive'] for p in targets):
            raise ValueError('Invalid game invitees')
        if not rules['min_players']<=1+len(targets)<=rules['max_players']:raise ValueError('Game player count mismatch')
        if type(stake) is not int or not 0<=stake<=c['max_stake'] or a['stock']+1e-9<stake:raise ValueError('Invalid/unaffordable stake')
        if settlement not in ('refund','winner_takes_all'):raise ValueError('Invalid agreed settlement')
        if sum(g['status'] in ('active','inviting') for g in m['games'].values())>=c['max_open_games']:raise ValueError('Game capacity reached')
        game='game'+str(m['next_game']);m['next_game']+=1;a['stock']=max(0.,a['stock']-stake)
        m['games'][game]={'host':aid,'artifact':key,'version':version,'kind':w['kind'],'source':item['content'],
            'rules':rules,'source_capacity':w.get('context_capacity',c['max_content_chars']),'players':[aid],'invited':list(targets),'stake':stake,'settlement':settlement,
            'exit_policy':'refund_all','escrow':{aid:stake},'state':copy.deepcopy(rules['initial_state']),
            'moves_completed':0,'status':'inviting' if targets else 'active','created':t,
            'invite_expires':t+c['game_invite_ttl']+1,'expires':t+c['game_max_rounds']+1,'active_round':None if targets else t}
        return {'game_created':game,'stake_locked':stake,'requires_explicit_consent':bool(targets)}
    if tool in ('join_game','decline_game','game_move','leave_game'):
        key=action.get('game');g=m['games'].get(key)
        if not g or g['status'] not in ('active','inviting'):raise ValueError('Game unavailable')
        if tool in ('join_game','decline_game'):
            if g['status']!='inviting' or aid not in g['invited'] or g['created']>=t or t>=g['invite_expires']:
                raise ValueError('No previously visible live invitation')
            if tool=='decline_game':return {'game_closed':close_game(state,key,g,'aborted')}
            if a['stock']+1e-9<g['stake']:raise ValueError('Cannot afford agreed stake')
            a['stock']=max(0.,a['stock']-g['stake']);g['escrow'][aid]=g['stake'];g['players'].append(aid);g['invited'].remove(aid)
            if not g['invited']:g.update(status='active',active_round=t,expires=t+c['game_max_rounds']+1)
            return {'game_joined':key,'stake_locked':g['stake'],'status':g['status']}
        if aid not in g['players']:raise ValueError('Not a joined game participant')
        if tool=='leave_game':return {'game_closed':close_game(state,key,g,'aborted')}
        if g['status']!='active' or t>=g['expires'] or g['active_round']>=t:raise ValueError('Game not previously active or expired')
        expected=action.get('expected_move')
        if type(expected) is not int or expected!=g['moves_completed']:raise ValueError('Game state changed since observed move')
        if g['rules']['turn_mode']=='alternating' and g['players'][expected%len(g['players'])]!=aid:
            raise ValueError('Not your game turn')
        move=action.get('move')
        if move is None:
            try:move=json.loads(action.get('move_json',''))
            except (TypeError,json.JSONDecodeError) as exc:raise ValueError('Invalid move_json') from exc
        if not isinstance(move,dict):raise ValueError('Game move must be a JSON object')
        result=transition(g['source'],g['kind'],g['state'],move,aid,g['players'],f'{cfg["seed"]}:{key}:{expected}:{aid}',g.get('source_capacity',c['max_content_chars']))
        g['state']=result['state'];g['moves_completed']+=1
        m['game_events'].append({'round':t,'game':key,'op':'move','actor':aid,'move':copy.deepcopy(move),'moves_completed':g['moves_completed']})
        closed=None
        if result['done']:closed=close_game(state,key,g,'finished',result.get('winner'))
        elif g['moves_completed']>=g['rules']['max_moves']:closed=close_game(state,key,g,'expired')
        return {'game':key,'state':copy.deepcopy(g['state']),'moves_completed':g['moves_completed'],'status':g['status'],'settlement':closed}
    raise ValueError('Unknown content action')
