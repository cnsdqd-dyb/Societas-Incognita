"""Actionable public-interface errors; no hidden recipe or private-state lookup."""


class InterfaceError(ValueError):
    def __init__(self, reason, code, field, message, hint, details=None):
        super().__init__(reason)
        self.feedback={'status':'rejected','code':code,'category':'resources' if code.startswith('INSUFFICIENT') else 'format',
                       'field':field,'message':message,'hint':hint,'details':details or {}}


# Exact known validation messages, not arbitrary exception text from internal code.
# Values: code, category, field, explanation, correction.
RULES={
 'Missing action object':('ACTION_OBJECT_REQUIRED','format','action','action 必须是 JSON 对象。','提交 action 对象，并填写 tool 及该动作的参数。'),
 'Missing communication object':('COMMUNICATION_OBJECT_REQUIRED','format','communication','communication 必须是 JSON 对象。','填写 op 和对应参数；结束自己的交流可使用 silent。'),
 'Duplicate basket material':('DUPLICATE_MATERIAL','format','inputs','同一材料在清单中重复出现。','将同一种材料的数量合并为一个条目。'),
 'Invalid basket':('BASKET_FORMAT','format','basket','材料清单必须是非空数组。','使用 [{"item":"A","amount":1}] 形式，每种材料最多一项。'),
 'Invalid basket entry':('BASKET_ENTRY_FORMAT','format','basket','清单条目必须且只能含 item 和 amount。','item 填材料标识，amount 填合法数值。'),
 'Insufficient assets':('INSUFFICIENT_ASSETS','resources','amount','自己的可用资产不足以支付本次操作。','核对自己的可用库存与数量；存入容器、托管或别人持有的材料不能直接支出。'),
 'Unknown material':('UNKNOWN_MATERIAL','reference','item','材料标识无效。','使用自己观察中出现的材料标识，保留原有大小写。'),
 'Unknown station or mode':('UNKNOWN_STATION_MODE','reference','facility/mode','设备或该设备的操作模式无效。','从自己可见的设备和模式中选择，不把配方猜测写成模式名。'),
 'Already has a pending experiment':('EXPERIMENT_PENDING','state','experiment','自己已有尚未结算的实验。','等待该实验结算后再提交，或选择其他合法动作。'),
 'Use material inputs at stations':('ENERGY_NOT_MATERIAL_INPUT','format','inputs','设备投料接口不接受 ENERGY。','投料使用持有的材料；可用能量另用于支付费用。'),
 'Cannot pay experiment operation cost':('INSUFFICIENT_OPERATION_ENERGY','resources','stock','可用能量不足以支付实验提交费用。','核对自己的可用能量，取得足够能量后再提交。'),
 'Item offer unavailable':('ITEM_OFFER_UNAVAILABLE','state','offer','这份材料报价不存在、已关闭或已到期。','使用自己可见且仍开放的材料报价 ID；已接受的报价不能再次接受。'),
 'Not eligible to accept offer':('ITEM_OFFER_PERMISSION','permission','offer','自己没有资格接受这份报价。','不能接受自己发布的报价；报价还须面向自己或公开，卖方须可交易。'),
 'Only seller can cancel':('ITEM_OFFER_OWNER_ONLY','permission','offer','只有报价发布者可以取消。','仅取消自己发布且仍开放的报价。'),
 'Recipient must be another living member':('INVALID_RECIPIENT','reference','target','目标必须是另一位当前存活的成员。','核对目标成员 ID；不能将自己作为转交目标。'),
 'Invalid transfer note':('TRANSFER_NOTE_FORMAT','format','note','转交说明必须是至多180字符的字符串。','无说明也请提交空字符串，不提交对象或数组。'),
 'Material discharge power exceeded':('DISCHARGE_LIMIT','capacity','amount','单次转为能量的数量超过当前放电限制。','核对自己可见的放电能力，分次处理或降低数量。'),
 'No visible pool for this material':('NO_VISIBLE_POOL','reference','item','当前没有可采集的该材料池。','从自己的观察中选择实际可采集的材料池。'),
 'Chat not visible at decision time':('CHAT_NOT_VISIBLE','visibility','chat','作决定时，这个聊天 ID 不在自己可见的会话中。','使用观察中的聊天 ID；新邀请需在下一交流步可见后才能操作。'),
 'Not member at decision time':('CHAT_NOT_JOINED','permission','chat','作决定时，自己尚不是该会话成员。','先接受自己可见的有效邀请，再在后续交流步发送。'),
 'Not a member at decision time':('CHAT_NOT_JOINED','permission','chat','作决定时，自己尚不是该会话成员。','先接受自己可见的有效邀请，再在后续交流步发送。'),
 'Physical action cannot exceed the pre-action communication allowance':('ACTION_PHASE_COMMUNICATION','phase','communication.op','动作阶段不能另开一轮交流。','在动作响应中使用 silent；对话放在动作前的交流阶段。'),
 'Game unavailable':('GAME_UNAVAILABLE','reference','game','该游戏不存在或不处于可参与状态。','使用游戏目录中的 game ID；聊天 ID 不能作为游戏 ID。'),
 'No previously visible live invitation':('GAME_INVITATION_REQUIRED','visibility','game','自己没有此前已可见的有效游戏邀请。','先查看自己可见的邀请，再加入对应游戏。'),
 'Not a joined game participant':('GAME_NOT_JOINED','permission','game','自己尚未加入该游戏。','先加入有效邀请的游戏，之后才能走棋或退出。'),
 'Game not previously active or expired':('GAME_NOT_ACTIVE','state','game','游戏尚未进入可行动状态，或已经结束、到期。','核对观察中的游戏状态；本轮刚启动的游戏在后续轮次行动。'),
 'Not your game turn':('GAME_TURN','state','game','当前不是自己的游戏回合。','按自己可见的轮流顺序行动。'),
 'Game state changed since observed move':('GAME_STALE_MOVE','state','expected_move','棋局步数与提交时的预期不一致。','重新观察最新棋局，使用当前 moves_completed 作为 expected_move。'),
 'Invalid move_json':('GAME_MOVE_JSON','format','move_json','move_json 不是合法 JSON。','使用双引号 JSON 对象，不提交 Python 字典文字或普通发言。'),
 'Game move must be a JSON object':('GAME_MOVE_OBJECT','format','move_json','游戏行动必须是 JSON 对象。','按照自己可见的游戏规则提交行动对象。'),
 'Work unavailable':('WORK_UNAVAILABLE','reference','artifact','作品不存在或当前不可用。','从自己可见的作品目录选择实际存在的 artifact ID。'),
 'Invalid work content':('WORK_CONTENT_FORMAT','format','content','作品内容不满足当前接口的类型或长度要求。','提交字符串，并核对自己可见的作品容量与格式要求。'),
 'Only the author may revise, publish or sell a work':('WORK_AUTHOR_ONLY','permission','artifact','只有作者可以修改、发布或出售这件作品。','选择自己创作的作品；获得阅读许可不等于获得作者身份。'),
 'No permission to read/use this version':('WORK_READ_PERMISSION','permission','artifact/version','自己没有读取或使用这个版本的许可。','使用公开版本，或先获得该版本的有效许可。'),
 'No readable work version':('WORK_VERSION_UNAVAILABLE','visibility','artifact/version','当前没有自己可读的作品版本。','查看作品可见性和已有许可。'),
 'Work offer unavailable or expired':('WORK_OFFER_UNAVAILABLE','state','offer','作品报价不可用或已到期。','选择自己可见且开放的作品报价。'),
 'Invalid work metadata':('WORK_METADATA_FORMAT','format','title/kind/visibility','作品元数据不合法。','按接口提交标题、支持的 kind 和 visibility。'),
 'Unavailable material action':('ACTION_UNAVAILABLE','availability','tool','动作未开放或自己当前不能行动。','核对观察中的工具列表和自己的状态。'),
 'Unavailable content tool':('ACTION_UNAVAILABLE','availability','tool','该内容工具当前未开放。','从自己可见的工具列表中选择。'),
 'Not an executable game work':('GAME_WORK_KIND','format','artifact/kind','这件作品不是可执行游戏。','普通 text 或研究笔记不能直接开局；使用符合契约的 game_xml 或 game_python 作品。'),
 'Invalid game XML':('GAME_XML_SYNTAX','format','content','游戏 XML 无法解析。','检查标签闭合与属性引号，按游戏 XML 契约提交。'),
 'Invalid game Python syntax':('GAME_PYTHON_SYNTAX','format','content','游戏 Python 存在语法错误。','核对 Python 语法以及受支持的游戏程序接口。'),
 'Invalid XML initial state':('GAME_INITIAL_JSON','format','initial','XML 初始状态不是合法 JSON。','使用双引号 JSON 对象作为初始状态。'),
 'Move rejected by game rules':('GAME_RULE_REJECTED','game_rule','move_json','这步行动被该游戏自身的规则拒绝。','核对自己可见的游戏规则与最新状态，选择允许的行动。'),
 'Function has not been privately discovered':('FUNCTION_NOT_DISCOVERED','knowledge','function','自己尚未发现这个组合功能。','只能使用自己已经获得私有说明与接口的功能。'),
 'Invalid function confirmation or target':('FUNCTION_CONFIRM_FORMAT','format','confirm','confirm 必须为布尔值。','使用 true 确认付费调用或 false 取消，不提交字符串。'),
 'Confirmed function needs a target':('FUNCTION_TARGET_REQUIRED','format','target','确认调用时必须指定目标字符串。','依据自己已发现的功能说明填写合法目标。'),
 'Combination materials are missing':('FUNCTION_MATERIALS_MISSING','resources','inventory','当前没有凑齐该功能所需的可用材料。','发现记录保留，但每次使用仍须持有所需材料；取消调用无需付费。'),
 'Function target is unavailable or unauthorized':('FUNCTION_TARGET_PERMISSION','permission','target','该目标不可用或自己无权作用于它。','依据自己已发现的功能说明及目标权限选择。'),
 'Only container owner can store or withdraw':('CONTAINER_OWNER_ONLY','permission','container','只有容器所有者可以直接存取。','使用自己的容器，或先与所有者协商。'),
 'Unknown material container':('CONTAINER_UNAVAILABLE','reference','container','容器标识无效。','使用自己可见的容器 ID。'),
 'Container capacity exceeded':('CONTAINER_FULL','capacity','amount','本次存入将超过容器容量。','核对容器的可见容量和已有存量，降低存入量。'),
 'Inactive members cannot act':('MEMBER_INACTIVE','availability','tool','自己当前处于非活跃状态，不能执行普通动作。','依据自己可见的状态与救援接口等待处理。'),
}


def feedback(exc, phase='action'):
    if isinstance(exc,InterfaceError):
        result=dict(exc.feedback)
    else:
        rule=RULES.get(str(exc))
        if rule:
            code,category,field,message,hint=rule
        elif isinstance(exc,KeyError):
            code,category,field,message,hint=('MISSING_FIELD','format',phase,'操作缺少必要字段或引用无效。','核对该动作的参数契约以及自己可见的对象 ID。')
        elif isinstance(exc,TypeError):
            code,category,field,message,hint=('FIELD_TYPE','format',phase,'操作参数的类型不符合接口。','核对字符串、数字、对象和数组的区别。')
        else:
            code,category,field,message,hint=('OPERATION_REJECTED','validation',phase,'本次操作未通过校验。','核对工具参数、自己的可用资源及可见对象状态。')
        result={'status':'rejected','code':code,'category':category,'field':field,
                'message':message,'hint':hint,'details':{}}
    result['phase']=phase
    return result


def record_error(outcome, phase, exc):
    detail=feedback(exc,phase)
    outcome[phase+'_error']=detail['message']
    outcome[phase+'_feedback']=detail


def experiment_feedback(record):
    if record['result']=='no_product':
        return {'status':'executed_no_output','code':'NO_OUTPUT',
                'message':'实验已合法执行并结算，本次未产生材料。',
                'hint':'这只反映本次投入、设备、模式和时点；根据自己的实验记录判断是否调整，不能据此断言所有条件下都无产物。'}
    return {'status':'executed','code':record['result'].upper(),
            'message':'实验已完成结算，请查看 produced 和实际费用记录。'}
