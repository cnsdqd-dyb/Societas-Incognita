rules = {
    "min_players": 2,
    "max_players": 2,
    "max_moves": 12,
    "turn_mode": "alternating",
    "initial_state": {"position": 0, "goal": 6},
    "description": "灯塔接力：两人轮流沿着海岸前进一格或两格，先走到第六格灯塔的人获胜。每次行动输入 step=1 或 step=2。海岸上的六盏小灯会随脚步依次亮起，终点是一座整夜等待归航的灯塔。"
}

# 这是一个可以独立玩的短游戏。想象两位夜行者在海边相遇，
# 他们决定用一场比赛决定谁先去敲灯塔的门。石阶上没有陷阱，
# 每个人都能选择走一格或两格，也能在自己的回合前想一想。
# 走到第四格时，海风会更响一些；第五格能看见门上的铜铃。
# 谁先走到第六格，谁就先讲一个故事给守灯人听。
# 用过的步数不必归还，灯光只是棋盘上的位置标记。
# 两人可以在下一局互换先后手，或者在纸上讨论不同的走法。
# 保存下来的这个版本只接受一格和两格，其他输入会被拒绝。

def transition(state, action, actor, players):
    step = action.get("step", 0)
    if step not in [1, 2] or state["position"] >= state["goal"]:
        return {"valid": False}
    state["position"] = min(state["goal"], state["position"] + step)
    done = state["position"] == state["goal"]
    return {"state": state, "done": done, "winner": actor if done else None}
