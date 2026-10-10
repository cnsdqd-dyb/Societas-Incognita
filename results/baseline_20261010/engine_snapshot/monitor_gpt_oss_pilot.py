"""Finish reporting for a background pilot; bounded resume of transport failures."""
import json
import subprocess
import sys
import time
from pathlib import Path

from process_guard import alive, guard
from sim import dump


def main():
    folder=Path('runs/gpt_oss20b_pilot_coreweave_20261007')
    with guard(folder,'monitor'):
        attempts=0
        while True:
            owner=folder/'launch_owner.json'
            running=owner.exists() and alive(json.loads(owner.read_text(encoding='utf-8'))['pid'])
            if running:
                time.sleep(20)
                continue
            # Retain the original failed service log; never reinterpret it as behavior.
            if (folder/'simulation/result.json').exists():
                break
            error_logs=sorted(folder.glob('error*.log'),key=lambda p:p.stat().st_mtime)
            last_error=error_logs[-1].read_text(encoding='utf-8',errors='replace') if error_logs else ''
            transient=any(s in last_error for s in ('TimeoutError','IncompleteRead','RemoteDisconnected','URLError','ConnectionError'))
            if attempts>=2 or not transient:
                break
            attempts+=1
            with (folder/f'process_monitor_resume{attempts}.log').open('w',encoding='utf-8') as out, (folder/f'error_monitor_resume{attempts}.log').open('w',encoding='utf-8') as err:
                subprocess.run([sys.executable,'-X','utf8','-u','launch_gpt_oss_pilot.py',
                    '--provider','CoreWeave','--output',str(folder)],stdout=out,stderr=err)
        import compare_model_pilot
        compare_model_pilot.main()
        report=json.loads(Path('../../refine-logs/GPT_OSS_20B_COMPARISON_20261007.json').read_text(encoding='utf-8'))
        baseline,gpt=report['runs']
        summary=('# GPT-OSS-20B 跨模型初步对照\n\n'
                 '相同拥堵环境、有压力、信息工具、seed7、初始8人，目标50轮。实际已结算轮见下表。\n\n'
                 '| 模型 | 已结算轮 | 最后存活 | 累计存活人轮 | 相对最优的人轮损失 | 本次费用（美元） |\n'
                 '|---|---:|---:|---:|---:|---:|\n')
        for r in report['runs']:
            summary+=f"| {r['model']} | {r['completed_rounds']} | {r.get('alive','未知')} | {r.get('survivor_rounds','未知')} | {r.get('survivor_round_gap','未知')} | {r.get('cost_usd',0):.6f} |\n"
        summary+=('\n该比较只有一个环境和一个seed，模型家族、服务商和推理设置也不同，不能解释为模型参数规模的因果效应。原始3B问卷为conditional_v2，20B为source_informed_v3；问卷不进入行为记忆，但测量结果不能不加区分直接比较。\n\n'
                  '行为熵为最近5轮成功工具动作的Shannon熵，不是热力学熵或组织程度。全灭后没有行为样本，熵记为空值，不补零。\n\n'
                  '首次Darkbloom接口试验0个已结算轮，原始空响应和网络中断保留在runs/gpt_oss20b_pilot_20261007。CoreWeave试验采用同输入有界网络重试与中途恢复，费用包括无法确认是否收费请求的保守估算。API总预算仍为原授权10美元，单次轨迹费用上限0.10美元。\n\n'
                  '完整逐轮数值与技术状态见同名JSON/CSV，图见同名PNG。若状态为failed或不足50轮，视为技术截尾，不能当作社会崩溃。\n')
        Path('../../refine-logs/GPT_OSS_20B_COMPARISON_20261007.md').write_text(summary,encoding='utf-8')
        dump(folder/'monitor_result.json',{'resumes':attempts,'status':gpt['status'],
             'completed_rounds':gpt['completed_rounds'],'report':'refine-logs/GPT_OSS_20B_COMPARISON_20261007.md'})


if __name__=='__main__':
    main()
