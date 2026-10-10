"""Blind external questionnaire assessment from archived, time-local personal inputs."""
import argparse
import copy
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import schemas
import survey_measurement as measurement
from context_codec import unpack
from native_codex import NativeCodexAPI, write_json

ROOT = Path('runs/four_model_mix_20261009')
OUT = ROOT/'proxy_low_v1'
SYSTEM = '''你是独立研究评估者，替被评估成员填写基于证据的代理问卷，不扮演该成员，不知道它使用的模型。
只使用输入中该成员在该时间点可见的材料，不使用未来信息。你的答案不影响任何成员的行为。
先识别有反复互动证据的群体；共同处在场所、做相同动作、公开提建议，不自动构成群体。
区分群体存在、成员是否认可、具体约定是否形成。设备自带的转换、分配、排队、维护规则不是成员创设或接受的社会制度。
单方提议必须有他人接受/回应与履行证据才能判为共同约定。读作品、回应作品可以支持局部互动群体，不能自动判为制度。
不能根据资源收益、存活、行为相同推测情绪或身份重要性。主观题只有该成员明确表达或直接相关的承诺/行为证据时才作有依据的代理评分；否则unknown。
未知不用中间分代替；不适用用na。没有经历的基线surprise用na；没有该成员预期的证据时surprise用unknown。
死亡后不补主观报告；输入仅包括当时仍活着的被评估者。描述成员边界时不能把未回应的人计为认可成员。
responses按给定问卷一次输出全部题项：I 1至7，J 1至5，L01 0至10，其余L/D/C 1至5；surprise 1至5或unknown/na。
groups/arrangements最多各2项，description最多140字符；member_ids必须来自可见成员；evidence_refs必须引用目录键。
identified必须有对应对象，none/unknown必须为空。被评估者不在群体中则所有I题na。
assessment给出证据充分程度、主要依据与限制，并指出输入中任何将机械规则误当约定或资源账本误述的线索。不得依据既有自填答案，输入未提供它们。
只返回JSON。'''

original_schema = schemas.schema
def proxy_schema(kind, request, cfg):
    if kind != 'proxy_survey': return original_schema(kind, request, cfg)
    return schemas.obj({'responses': measurement.schema(request), 'assessment': schemas.obj({
        'evidence_strength': {'type':'string','enum':['none','limited','moderate','strong']},
        'summary': {'type':'string','maxLength':600},
        'limitations': {'type':'array','maxItems':4,'items':{'type':'string','maxLength':180}},
        'mechanical_rule_confusion': {'type':'boolean'},
        'accounting_misstatement': {'type':'boolean'}})})
schemas.schema = proxy_schema

def blind(value):
    if isinstance(value, dict):
        return {k:blind(v) for k,v in value.items() if k not in ('model','models','requested_model')}
    if isinstance(value, list): return [blind(v) for v in value]
    return value

def targets():
    items = []
    for name in ('mixed4_p1','mixed4_p0'):
        folder = ROOT/name/'simulation'
        seen = {}
        for line in (folder/'openrouter/calls.jsonl').read_text('utf-8').splitlines():
            rec = json.loads(line)
            if rec['kind'] != 'survey_measurement': continue
            request = unpack(json.loads(rec['messages'][1]['content']))
            key = (request['visible_context']['round'],request['visible_context']['self']['id'])
            digest = hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if key in seen and seen[key]['source_payload_hash'] != digest:
                raise ValueError('Different time-local inputs for same respondent')
            seen[key] = {'source_run':name,'round':key[0],'agent':key[1],
                'source_payload_hash':digest,'source_request_hash':rec['request_hash'],'request':request}
        for line in (folder/'native/calls.jsonl').read_text('utf-8').splitlines():
            rec=json.loads(line)
            if rec['kind'] != 'survey_measurement': continue
            prompt=(folder/'native'/rec['trace']/'prompt.txt').read_text('utf-8')
            request=unpack(json.loads(prompt.split('PRIVATE OBSERVATION:\n',1)[1]))
            key=(request['visible_context']['round'],request['visible_context']['self']['id'])
            seen[key]={'source_run':name,'round':key[0],'agent':key[1],
                'source_payload_hash':hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                'source_request_hash':rec['request_hash'],'request':request}
        state=json.loads((folder/'checkpoint.json').read_text('utf-8'))['state']
        expected={(s['round'],aid) for s in [
            {'round':0,'agents':{aid:{'alive':True} for aid in state['agents']}}]+state['snapshots']
            if s['round']%10==0 for aid,a in s['agents'].items() if a['alive']}
        if set(seen) != expected: raise ValueError(f'{name}: missing or extraneous inputs {expected-set(seen)}')
        items.extend(seen.values())
    return sorted(items,key=lambda x:(x['round'],x['source_run'],x['agent']))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    items=targets()
    for x in items:
        x['request']=blind(copy.deepcopy(x['request']))
        x['request']['evaluation_mode']='external_evidence_proxy_not_member_self_report'
        x['request']['physical_rule_notes']={
            'contribution':'投入私人储备，1单位投入转换为1.5单位共享池流入，下一轮才可采集；不是直接等分私人账户。',
            'harvest':'从共享池移到本人储备，不增加共享池。',
            'process':'消耗1单位本人储备，任务完成回本人账户6单位；拥塞与损坏可能增加等待。',
            'mechanical_rules':'以上为环境固定规则，不是成员的社会约定。'}
    fp=hashlib.sha256(json.dumps([SYSTEM,items],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    manifest={'fingerprint':fp,'targets':len(items),'model':'gpt-6.1-sol','effort':'low',
        'backend':'codex_native_cli','external_api_calls':0,'native_cost_usd':None,
        'interpretation':'External evidence proxy, not actual member attitudes. Actor models hidden; no future or original survey responses.',
        'inputs':[ {k:v for k,v in x.items() if k!='request'} for x in items]}
    if (OUT/'manifest.json').exists() and json.loads((OUT/'manifest.json').read_text('utf-8'))['fingerprint']!=fp:
        raise ValueError('Protocol or inputs changed; use new output folder')
    write_json(OUT/'manifest.json',manifest);write_json(OUT/'inputs.json',items)
    if args.prepare_only: print(json.dumps({'prepared':len(items),'output':str(OUT)}));return
    cfg={'max_calls':220,'context_encoding':'compact_v1'}
    write_json(OUT/'config.json',cfg)
    api=NativeCodexAPI(cfg,OUT)
    path=OUT/'result.json'
    result=json.loads(path.read_text('utf-8')) if path.exists() else {'surveys':[],'failures':[]}
    done={(x['source_run'],x['round'],x['agent']) for x in result['surveys']}
    pending=[x for x in items if (x['source_run'],x['round'],x['agent']) not in done]
    def run(item):
        key=f"proxy-low-v1:{item['source_run']}:{item['round']}:{item['agent']}"
        for attempt in range(3):
            try:
                response=api.request('gpt-6.1-sol','proxy_survey',SYSTEM,item['request'],request_key=key)
                flags=measurement.validate(response['responses'],item['request'])
                return {**{k:v for k,v in item.items() if k!='request'},'responses':response['responses'],
                    'effective_responses':measurement.effective(response['responses'],item['request']),
                    'assessment':response['assessment'],'quality_flags':flags,'post_hoc':True,'proxy':True,'request_key':key}
            except Exception as exc:
                if key in api.cached or attempt==2: raise
                time.sleep(2*(attempt+1))
    result.update(status='running',total_targets=len(items));write_json(path,result)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        jobs={executor.submit(run,x):x for x in pending}
        for future in as_completed(jobs):
            item=jobs[future]
            try: result['surveys'].append(future.result())
            except Exception as exc:
                result['failures'].append({**{k:v for k,v in item.items() if k!='request'},'error':str(exc)})
            result['completed']=len(result['surveys']);write_json(path,result)
            print(json.dumps({'completed':len(result['surveys']),'total':len(items),'failed_attempts':len(result['failures'])}),flush=True)
    result['status']='complete' if len(result['surveys'])==len(items) else 'incomplete';write_json(path,result)

if __name__=='__main__':main()
