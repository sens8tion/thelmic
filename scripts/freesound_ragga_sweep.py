"""Sit on Freesound and pull a load of ragga / dub / jungle-relevant
material. Filters to CC0 / Creative Commons 0 / Attribution licenses
so everything's safely reusable.

Saves to .thelmic/samples/freesound/ via the adapter cache, then
mirrors curated picks to the Ableton User Library Splice/BBC/Freesound
folder so Live's path resolver picks them up.
"""
from __future__ import annotations
import os, shutil
from pathlib import Path
from collections import defaultdict

from thelmic import sources
from thelmic.sources import freesound


# Categories to sweep — each tuple: (label, query, want_oneshot, max_dur, top_n)
SWEEPS = [
    ('horns_brass',     'reggae horn stab brass',          True,  3,  6),
    ('organ_skank',     'reggae organ skank chord',        True,  4,  6),
    ('dub_siren',       'dub siren wobble',                False, 8,  4),
    ('vinyl_crackle',   'vinyl crackle hiss',              False, 30, 4),
    ('vocal_toast',     'reggae vocal toast dancehall',    True,  4,  6),
    ('sub_bass_drone',  'sub bass drone deep low',         False, 30, 4),
    ('reverse_crash',   'reverse cymbal crash',            True,  6,  4),
    ('tape_stop',       'tape stop reel rewind',           True,  5,  4),
    ('snare_roll',      'snare roll fill',                 True,  4,  4),
    ('riser_impact',    'riser sweep up tonal',            True,  6,  4),
    ('ragga_drum',      'ragga jungle drum break',         False, 10, 4),
    ('crowd_noise',     'crowd applause cheer',            False, 12, 3),
    ('rim_perc',        'rim shot percussion wood',        True,  2,  4),
    ('bell_chime',      'bell chime stab tonal',           True,  3,  4),
]

# Acceptable: CC0 (publicdomain/zero) and CC-BY (licenses/by/, not by-nc/by-nd/by-sa).
# Freesound returns license as a URL.
ACCEPT_LICENSES = ('publicdomain/zero',)        # CC0 — anything goes
ACCEPT_BY = '/licenses/by/'                      # CC-BY — must NOT contain by-nc/by-nd

USER_LIB_DST = Path.home() / 'Documents' / 'Ableton' / 'User Library' / 'Samples' / 'Freesound'
USER_LIB_DST.mkdir(parents=True, exist_ok=True)


def is_acceptable(lic: str | None) -> bool:
    if not lic:
        return False
    s = lic.lower()
    # CC0 — universally OK
    if any(k in s for k in ACCEPT_LICENSES):
        return True
    # CC-BY (plain attribution) — accepted; reject any -nc / -nd / -sa variants
    if ACCEPT_BY in s and 'by-nc' not in s and 'by-nd' not in s and 'by-sa' not in s:
        return True
    return False


def main() -> None:
    print(f'available sources: {sources.list_sources()}\n')
    if 'freesound' not in sources.list_sources():
        print('Freesound not available — bailing'); return

    by_label: dict[str, list] = defaultdict(list)
    fetched_count = 0
    skipped_license = 0

    for label, query, want_oneshot, max_dur, top_n in SWEEPS:
        print(f'--- {label}: {query!r}  (max_dur={max_dur}s, top={top_n}) ---')
        try:
            kwargs = {'limit': top_n * 3, 'max_duration': max_dur}
            hits = freesound.search(query, **kwargs)
        except Exception as e:
            print(f'  search fail: {e}')
            continue
        kept = []
        for h in hits:
            if not is_acceptable(h.license):
                skipped_license += 1
                continue
            kept.append(h)
            if len(kept) >= top_n:
                break
        if not kept:
            print(f'  no acceptable-license hits\n')
            continue
        for h in kept:
            try:
                cached = sources.fetch(h)
                # Mirror with descriptive name to User Library
                safe_title = ''.join(c if c.isalnum() or c in '-_' else '_'
                                     for c in (h.title or 'untitled'))[:60]
                ext = cached.suffix or '.mp3'
                dst_name = f'FS_{label}_{h.id}_{safe_title}{ext}'
                dst = USER_LIB_DST / dst_name
                if not dst.exists() or dst.stat().st_size != cached.stat().st_size:
                    shutil.copy2(cached, dst)
                size_kb = dst.stat().st_size // 1024
                print(f'  + {label:18s} {h.id:>10s}  {h.title[:40]!r:42s}  {size_kb}KB  lic={h.license[:24]!r}')
                by_label[label].append((h, dst))
                fetched_count += 1
            except Exception as e:
                print(f'  fetch fail [{h.id}]: {e}')
        print()

    print('\n=== summary ===')
    print(f'  fetched: {fetched_count}')
    print(f'  skipped (NC/incompatible license): {skipped_license}')
    print(f'  by label:')
    for label, items in sorted(by_label.items()):
        print(f'    {label:18s} {len(items)}')
    print(f'\n  User Library destination: {USER_LIB_DST}')


if __name__ == '__main__':
    main()
