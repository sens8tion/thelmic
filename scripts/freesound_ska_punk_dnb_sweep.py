"""Second Freesound pass — ska/punk + hardcore/dnb material for the arc
expansion: scenes 6-7 ska/punk pivot, scenes 8+ hardcore/dnb.

Same license filter as the ragga sweep (CC0 + CC-BY only).
"""
from __future__ import annotations
import os, shutil
from pathlib import Path
from collections import defaultdict

from thelmic import sources
from thelmic.sources import freesound


SWEEPS = [
    # --- SKA / PUNK side ---
    ('ska_upstroke',     'ska upstroke guitar offbeat',      True,  4,  4),
    ('ska_horn_stab',    'ska horn brass riff',              True,  4,  4),
    ('punk_drum_fast',   'punk drum loop fast',              False, 8,  4),
    ('punk_vocal_shout', 'punk vocal shout yell',            True,  3,  4),
    ('power_chord',      'distorted guitar power chord',     True,  3,  4),
    ('ska_beat',         'ska beat 2-tone rude boy',         False, 12, 4),
    # --- HARDCORE / DNB side ---
    ('amen_break',       'amen break drum loop',             False, 12, 4),
    ('jungle_break',     'jungle drum break',                False, 10, 4),
    ('dnb_break',        'drum bass break loop',             False, 10, 4),
    ('dnb_snare',        'dnb snare crack neuro',            True,  3,  4),
    ('hoover',           'hoover synth rave',                True,  4,  4),
    ('gabber_kick',      'hardcore kick distorted gabber',   True,  3,  4),
    ('riser_noise',      'noise riser sweep up',             True,  6,  3),
    ('impact_hit',       'cinematic impact hit boom',        True,  4,  3),
    ('reece_bass',       'reese bass dnb wobble',            True,  6,  3),
]

# CC0 + CC-BY plain attribution (reject -nc / -nd / -sa)
def is_acceptable(lic):
    if not lic:
        return False
    s = lic.lower()
    if 'publicdomain/zero' in s:
        return True
    if '/licenses/by/' in s and 'by-nc' not in s and 'by-nd' not in s and 'by-sa' not in s:
        return True
    return False


USER_LIB_DST = Path.home() / 'Documents' / 'Ableton' / 'User Library' / 'Samples' / 'Freesound'
USER_LIB_DST.mkdir(parents=True, exist_ok=True)


def main():
    print(f'available: {sources.list_sources()}\n')
    by_label = defaultdict(list)
    fetched = 0; skipped = 0
    for label, query, _, max_dur, top_n in SWEEPS:
        print(f'--- {label}: {query!r} (max_dur={max_dur}s, top={top_n}) ---')
        try:
            hits = freesound.search(query, limit=top_n * 4, max_duration=max_dur)
        except Exception as e:
            print(f'  search fail: {e}')
            continue
        kept = []
        for h in hits:
            if not is_acceptable(h.license):
                skipped += 1
                continue
            kept.append(h)
            if len(kept) >= top_n: break
        if not kept:
            print('  no acceptable-license hits\n'); continue
        for h in kept:
            try:
                cached = sources.fetch(h)
                safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in (h.title or 'untitled'))[:60]
                ext = cached.suffix or '.mp3'
                dst = USER_LIB_DST / f'FS_{label}_{h.id}_{safe}{ext}'
                if not dst.exists() or dst.stat().st_size != cached.stat().st_size:
                    shutil.copy2(cached, dst)
                kb = dst.stat().st_size // 1024
                print(f'  + {label:18s} {h.id:>10s}  {h.title[:40]!r:42s}  {kb}KB')
                by_label[label].append((h, dst))
                fetched += 1
            except Exception as e:
                print(f'  fetch fail [{h.id}]: {e}')
        print()
    print('\n=== summary ===')
    print(f'  fetched: {fetched}    skipped: {skipped}')
    for label, items in sorted(by_label.items()):
        print(f'    {label:18s} {len(items)}')


if __name__ == '__main__':
    main()
