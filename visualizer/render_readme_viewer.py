"""Capture the real viewer and encode a 16x playback excerpt for GitHub."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / 'docs/images'
FRAMES = ROOT / 'output/playwright/readme-replay-frames'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8776')
    parser.add_argument('--seconds', type=int, default=16)
    args = parser.parse_args()
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise SystemExit('Install ffmpeg to encode the GIF.')
    MEDIA.mkdir(parents=True, exist_ok=True)
    FRAMES.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1800, 'height': 1450}, device_scale_factor=1)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(args.url)
        page.wait_for_selector('#loading.hidden', state='attached')
        rid = page.evaluate("runs.find(r=>r.group==='sol_low'&&r.rounds>3)?.id || runs.find(r=>r.rounds>3)?.id")
        if not rid:
            raise RuntimeError('A recorded run with at least four completed rounds is required.')
        page.locator('#run').select_option(rid)
        page.wait_for_function('(id)=>data?.meta.id===id && document.getElementById("loading").classList.contains("hidden")', arg=rid)
        # Freeze this browser's source snapshot while the actual experiment continues.
        payload = page.evaluate('data')
        page.route('**/api/run?*', lambda route: route.fulfill(json=payload))
        completed = payload['meta']['rounds']
        start = next((e['round'] for e in payload['events']
                      if e.get('decision', {}).get('action', {}).get('tool') == 'experiment'), 1)
        start = min(start, completed - 3)
        page.locator('#speed').select_option('16')
        page.locator('#speechDuration').select_option('0.5')
        page.evaluate('(r)=>seek(r)', start)
        page.wait_for_timeout(300)
        # Include the three-column interface and material panel in the still.
        page.screenshot(path=str(MEDIA / 'viewer-interface-planets-v2.png'))
        # Keep the world, speech bubbles, timeline controls, and visible 16x label.
        clip = page.evaluate('''()=>{
          const a=document.querySelector('.world-top').getBoundingClientRect();
          const b=document.querySelector('.replay-options').getBoundingClientRect();
          return {x:a.x,y:a.y,width:a.width,height:b.bottom-a.top};
        }''')
        page.clock.install()
        page.clock.pause_at(page.evaluate('Date.now()'))
        # A DOM click preserves the crop; Playwright's pointer click can scroll controls into view.
        page.evaluate("document.getElementById('play').click()")
        fps = 12
        for index in range(args.seconds * fps):
            page.clock.run_for((index + 1) * 1000 // fps - index * 1000 // fps)
            page.screenshot(path=str(FRAMES / f'frame-{index:04d}.png'), clip=clip)
        end = page.evaluate('round')
        scenery = page.evaluate('({version:worldScene.terrain.layoutVersion,layout_seed:worldScene.seed,traits:worldScene.planet})')
        assert end > start, (start, end)
        assert page.evaluate('speed') == 16
        assert not errors, errors
        browser.close()
    filters = 'fps=12,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4'
    subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-framerate', str(fps),
                    '-i', str(FRAMES / 'frame-%04d.png'), '-frames:v', str(args.seconds*fps),
                    '-filter_complex', filters, '-loop', '0', str(MEDIA/'viewer-replay-planets-v2-16x.gif')], check=True)
    (MEDIA/'viewer-capture.json').write_text(json.dumps({'run': rid, 'completed_rounds': completed,
        'start_round': start, 'end_round': end, 'playback_speed': 16, 'dialogue_hold_seconds': .5,
        'capture_seconds': args.seconds, 'frames_per_second': fps,
        'source': 'browser render of recorded checkpoint; no model calls',
        'scenery': scenery,
        'coordinate_semantics': 'presentation_grid_not_simulation_positions'}, indent=2), encoding='utf-8')
    print(f'Captured interface and {args.seconds}s playback at 16x: R{start}–R{end}.')


if __name__ == '__main__':
    main()
