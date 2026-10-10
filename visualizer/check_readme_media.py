"""Check asset references, SVG animation timing and actual diagram accounting."""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[1]
for name in ('README.md', 'README.zh-CN.md'):
    content = (root / name).read_text(encoding='utf-8')
    for destination in re.findall(r'\]\(([^)]+)\)', content):
        if not destination.startswith(('http:', 'https:', '#')):
            assert (root / destination).exists(), (name, destination)
    for destination in re.findall(r'src="([^"]+)"', content):
        assert (root / destination).exists(), (name, destination)
    assert len(re.findall(r'src="docs/images/mechanisms/\d{2}\.svg"', content)) == 20
    assert content.index('docs/images/mechanisms/01.svg') < content.index('docs/images/compositional-world-laws.svg')
english = (root / 'README.md').read_text(encoding='utf-8')
assert english.startswith('# How do societies discover')
assert 'README.zh-CN.md' in english
assert '](docs/images/compositional-world-laws.svg)' in english
ns = '{http://www.w3.org/2000/svg}'
tree = ET.parse(root / 'docs/images/compositional-world-laws.svg')
assert not tree.findall('.//'+ns+'script')
assert len(tree.findall('.//'+ns+'animateMotion')) >= 8
for anim in tree.findall('.//'+ns+'animate'):
    if anim.get('values'):
        assert len(anim.get('values').split(';')) == len(anim.get('keyTimes').split(';'))
        times = list(map(float, anim.get('keyTimes').split(';')))
        assert times == sorted(times)
data = json.loads((root / 'docs/images/compositional-world-laws-data.json').read_text(encoding='utf-8'))
assert all(abs(f['accounting']['residual']) <= 1e-7 for f in data['frames'])
assert any(e['action']['tool']=='give_item' and not e['outcome'].get('error') for f in data['frames'] for e in f['events'])
assert sum(a['inventory']['S'] for a in data['frames'][-1]['agents'].values()) > 0
gif = Image.open(root / 'docs/images/mechanism-combinations.gif')
assert gif.n_frames >= 30 and gif.info.get('loop') == 0
print('English/Chinese README links, animated SVG, GIF loop, actual transfers, production and conservation: PASS')
