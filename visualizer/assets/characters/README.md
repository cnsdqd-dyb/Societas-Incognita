# Four-direction pixel characters

`agent-north.svg`, `agent-south.svg`, `agent-east.svg`, and `agent-west.svg` are the editable base poses used by the sandbox's directional sprite vocabulary.

The viewer generates each member's variations from `directionalActorSVG` in `sandbox-25d.js`: hair, clothing color, skin tone, walking frames and held objects. World-space movement selects the facing direction; camera rotation selects the corresponding screen pose.

Regenerate these base SVGs and check navigation, collisions and picking with `python visualizer/check_sandbox_browser.py`, while the local viewer is running.
