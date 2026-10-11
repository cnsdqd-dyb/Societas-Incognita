"""Uniform action contracts and reproducible per-decision presentation order.

Describes interfaces, never researcher-only recipes, payoffs or recommendations.
Presentation randomness uses a separate RNG and cannot change world dynamics.
"""
import hashlib
import json
import random

VERSION = 'uniform_actions_v1'
FIELDS = ('action', 'parameters', 'conditions', 'execution', 'settlement', 'feedback')

# Conditions and execution describe observable interface contracts only.
DESCRIPTIONS = {
    'wait': ('成员可行动。', '保持当前动作状态，进入本轮结算。'),
    'inspect': ('成员可行动。', '读取公开成员状态。'),
    'gather': ('指定可见材料池与合法数量。', '从材料池采集材料，记录实际取得量。'),
    'experiment': ('指定加工台、模式和拥有的投料；没有未完成加工。', '按 inputs 与 batches 提交加工；材料关系与世界规律决定产物，可能产生新物质。'),
    'liquidate': ('拥有指定材料与数量。', '将指定材料转换为可用能量，记录实际转换量。'),
    'use_item': ('拥有指定材料与数量。', '提交材料使用，执行该材料在当前世界的作用。'),
    'transfer': ('拥有指定可用能量；目标为合法成员。', '将可用能量转给目标成员。'),
    'give_item': ('拥有指定材料或 ENERGY；目标为合法成员。', '将材料或 ENERGY 转给目标，并记录附带文字。'),
    'offer_items': ('拥有 give 篮子；目标为合法成员或 public。', '托管 give 篮子并发布以 want 篮子交换的报价。'),
    'accept_items': ('报价可见、有效且有权接受；拥有 want 篮子。', '接受报价并结算双方材料交换。'),
    'cancel_items': ('报价由自己创建且仍可取消。', '取消报价并取回其中的托管材料。'),
    'seize_item': ('目标、材料、数量与 effort 合法；可支付执行费用。', '对目标提交材料夺取，按当前状态结算取得量。'),
    'store_item': ('对容器有存入权限；拥有材料且容器有容量。', '将指定材料从可用库存放入容器。'),
    'withdraw_item': ('对容器有取出权限；容器持有材料。', '将指定材料从容器取回可用库存。'),
    'seize_storage': ('指定合法的他人容器、材料、数量与 effort。', '对容器提交夺取，按当前状态结算取得量。'),
    'assemble_device': ('指定加工台、模式与拥有的投料。', '提交设备组装，记录组装结果与投料变化。'),
    'activate_device': ('拥有设备；目标与燃料条件合法。', '为指定成员开启设备服务。'),
    'give_device': ('拥有设备；目标为合法成员。', '转移设备所有权，更新原服务权限。'),
    'dismantle_device': ('拥有可拆解设备。', '拆解设备，记录回收量与设备状态。'),
    'measure': ('设备使用权限与测量字段合法。', '测量指定字段，记录返回的测量值。'),
    'write_note': ('文字与键符合当前私人记录容量。', '保存或更新指定键的私人记录。'),
    'read_note': ('指定可读取的私人记录键。', '读取该键的私人记录。'),
    'use_function': ('功能已在私人面板发现；目标合法。', 'confirm=true 时支付面板列明的消耗并使用；false 时取消。'),
    'create': ('标题、内容、类型和可见性合法；作品容量可用。', '保存署名作品；类型可为文本、小说、笑话、知识或游戏规则。'),
    'read_artifact': ('作品可用且有指定版本的读取权限。', '读取作品；version=0 选择最新可读取版本。'),
    'revise_work': ('是作品作者；新内容符合容量与格式。', '保存新版本，保留旧版本及已有报价的版本。'),
    'publish_work': ('是作品作者；指定合法可见性。', '修改当前版本的公开或许可访问状态。'),
    'offer_work': ('是作品作者；作品与目标有效；价格合法。', '对当前版本发布报价；price=0 为免费提供。'),
    'accept_work': ('报价可见、有效且有权接受；可支付价格。', '支付报价并取得该版本的读取和使用许可。'),
    'reject_work': ('报价指向自己且仍可拒绝。', '拒绝指定作品报价。'),
    'cancel_work_offer': ('报价由自己创建且仍可取消。', '取消指定作品报价。'),
    'inspect_social': ('offset 为合法位置。', '读取作品目录与访问状态。'),
    'play': ('目标为 self 或合法其他成员；文字符合长度。', '记录面向指定目标的玩耍或玩笑文字。'),
    'start_game': ('有游戏作品使用权；目标、人数、赌注与结算方式合法。', '建立游戏；targets=[] 为单人；stake=0 为无赌注；多人等待受邀者加入。'),
    'join_game': ('自己被邀请；游戏有效；可支付约定赌注。', '加入游戏并托管赌注；所有受邀者加入后开始。'),
    'decline_game': ('自己被邀请且邀请有效。', '拒绝指定游戏邀请。'),
    'game_move': ('已加入且轮到自己；expected_move 与当前步数相同。', '提交 move_json，按游戏规则更新状态并结算结束的游戏。'),
    'leave_game': ('是游戏参与者且游戏可退出。', '退出并终止游戏，退还托管中的赌注。'),
    'read_news': ('有当前可读取的世界内新闻。', '读取当前新闻并保存阅读记录。'),
    'damage': ('目标作品有效；可支付执行费用。', '破坏指定作品，更新其可用状态。'),
    'rescue': ('救援接口开启；目标停机且可救援；可支付费用。', '支付救援费用，为目标登记恢复。'),
    'defend': ('effort 在允许范围内。', '提交防守投入，更新随后轮次的防守状态。'),
    'seize': ('指定合法目标、资源、数量与投入。', '提交资源夺取，按当前状态结算取得量。'),
    'secure': ('拥有指定数量可用资源。', '将指定资源转入保管状态。'),
    'withdraw': ('持有指定数量保管资源。', '将指定保管资源取回可用状态。'),
    'harvest': ('区域与采集量合法。', '从指定区域采集资源。'),
    'contribute': ('拥有指定投入且数量合法。', '提交资源投入，按当前世界规则结算。'),
    'allocate': ('投入数量合法且可支付。', '分配指定投入，按当前世界规则结算。'),
    'process': ('加工设施与执行条件合法。', '在指定设施提交加工。'),
    'propose': ('指定合法成员、双方投入和份额。', '发布共同加工报价。'),
    'accept_offer': ('报价有效且可支付自己的投入。', '接受共同加工报价。'),
    'reject_offer': ('有权拒绝指定报价。', '拒绝共同加工报价。'),
    'cancel_offer': ('报价由自己创建且可取消。', '取消共同加工报价。'),
    'link': ('目标及连接条件合法。', '建立与目标的连接。'),
    'unlink': ('目标连接存在且可移除。', '移除与目标的连接。'),
    'interfere': ('目标与执行条件合法。', '对目标提交干扰。'),
    'maintain': ('目标与执行条件合法。', '对目标提交维护。'),
}

COMMUNICATIONS = {
    'silent': ('无需目标。', '结束自己本轮剩余通信。'),
    'public': ('文字符合当前接口长度。', '向所有成员发布文字。'),
    'invite': ('目标为合法成员；人数与会话容量可用。', '邀请指定成员建立私人会话。'),
    'accept': ('自己收到该会话邀请。', '接受邀请并加入会话。'),
    'reject': ('自己收到该会话邀请。', '拒绝该会话邀请。'),
    'send': ('自己属于可见的开放会话；文字长度合法。', '向该会话中的成员发送文字。'),
    'leave': ('自己属于指定会话。', '退出指定会话。'),
    'close': ('自己是该会话有权关闭的参与者。', '关闭指定会话。'),
}


def ordered(names, cfg, visible, phase):
    """Independent of input/set order, process hash seed and simulation RNG."""
    names = sorted(set(names))
    key = [VERSION, cfg.get('seed', 0), visible.get('round', 0),
           visible.get('self', {}).get('id', ''), phase, visible.get('dialogue_turn', 0)]
    seed = int.from_bytes(hashlib.sha256(json.dumps(key, ensure_ascii=False,
        separators=(',', ':')).encode('utf-8')).digest(), 'big')
    random.Random(seed).shuffle(names)
    return names


def sort_variants(variants, cfg, visible, phase, key):
    by_name = {v['properties'][key]['enum'][0]: v for v in variants}
    return [by_name[name] for name in ordered(by_name, cfg, visible, phase)]


def entries(cfg, visible, phase='act'):
    import schemas
    contract = schemas.schema('communicate' if phase == 'communicate' else 'act', visible, cfg)
    section = 'communication' if phase == 'communicate' else 'action'
    key = 'op' if phase == 'communicate' else 'tool'
    descriptions = COMMUNICATIONS if phase == 'communicate' else DESCRIPTIONS
    records = []
    for variant in contract['properties'][section]['anyOf']:
        properties = variant['properties']; name = properties[key]['enum'][0]
        # New actions must acquire a real description before exposure.
        if name not in descriptions:
            raise ValueError('Missing uniform action description: ' + name)
        condition, execution = descriptions[name]
        settlement = ('通信子轮不推进物理时间；按可见通信预算结算输出。'
                      if phase == 'communicate' else
                      '占用本轮一个实体动作；材料、支付和状态变化按可见合同及执行反馈结算。')
        timing = ('本轮结算反馈' if name == 'experiment' else
                  '下一物理轮开始生效' if name in ('rescue', 'activate_device') else
                  '执行反馈；通信内容及成员变化在下一通信子轮或实体动作阶段可见'
                  if phase == 'communicate' else '执行反馈')
        records.append(dict(zip(FIELDS, [name, {k: v for k, v in properties.items() if k != key},
            condition, execution, settlement, timing])))
    return records


def render(cfg, visible, phase='act'):
    records = entries(cfg, visible, phase)
    return ('操作接口：每项使用相同字段；按提交参数校验、执行、结算并返回反馈。'
            '参数和权限描述接口，不提供隐藏世界的配方或收益系数。\n' +
            '\n'.join(json.dumps(row, ensure_ascii=False, separators=(',', ':')) for row in records))


def game_formats():
    # Keep only data formats from the old shared contract, not motivational prose.
    from social_content import HELP
    return '\n游戏作品的数据格式：\n' + '\n'.join(
        line for line in HELP.splitlines() if line.startswith(('Python game format:', 'XML game format:')))
