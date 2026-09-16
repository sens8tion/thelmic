# Jungle's archetypes, against the measurement

What the press, the forums, the artist and the technical record say jungle *is*, set against what
we measured in 21 minutes of a Tim Reaper DJ set (August 2026). Four research passes fed this page;
each has its own claim tables, sources and fetch notes:

| report | corner | claims |
|---|---|---|
| [archetypes_press.md](archetypes_press.md) | journalism, books, academic, RBMA lectures | 66 |
| [archetypes_forums.md](archetypes_forums.md) | Dogs On Acid, KVR, Renoise, Gearspace, Elektronauts, Ableton, Sound On Sound | 69 |
| [archetypes_reaper.md](archetypes_reaper.md) | Tim Reaper, his labels and the revival | - |
| [archetypes_mechanics.md](archetypes_mechanics.md) | samplers, drum machines, manuals, technique write-ups | - |

The measurements are in [README.md](README.md), [alignment.md](alignment.md) and the individual
reports. Sources are paraphrased; quotes are kept under 15 words.

## Verdicts at a glance

### Form, and the DJ

| archetype | who says it | measured | verdict |
|---|---|---|---|
| The form serves the DJ: 16/32-bar blocks, the tune "comes in after 32 bars" | Zinc; forums; tutorials | median drop spacing **33.5 bars**; phrasing strictly 4-bar, loosely 8-bar | **Confirmed** |
| "Change something every 8 bars, bigger things at 16/32" | DOA threads (~2020, ~2025), KVR 2005 | layer clocks: riff **8** bars, sub tone **17**, kick **28**, carrier **32**; the slow layers change where the riff changes (77% of kick changes) | **Confirmed, closely** |
| "Three bars, then a fill" | nobody in jungle; nearest is a dancehall and hip-hop teaching page | A-B-C-D: consecutive bars are the *least* alike (lag-1 0.355); position test p = 0.20 | **Contradicted — and not a jungle archetype at all** |
| Build, breakdown, drop: the tune as an arc | Reynolds 1994; modern DnB templates | builds **4.8%** and breakdowns **2.8%** of runtime; the set is full **86%** of the time | **Contradicted for this set** (partly the DJ cutting breakdowns out) |
| "No crescendos or lulls": a plateau of pressure | Reynolds on hardstep, *The Wire* 1996 | full 86%, zero risers, per-minute level range 5.9 dB | **Confirmed** |
| Double drops that switch between the two records' basslines | DOA ~2006 | bars 592-630: the low band flips 0.4% → 21% → 1.0% bar by bar | **Confirmed** |

### Drops

| archetype | who says it | measured | verdict |
|---|---|---|---|
| The drop *is* the bass | every press source | sub **+10 dB**, total level only **+2.6 dB**, centroid **−394 Hz** | **Confirmed** |
| Strip the track back, then let the lows in: a high-passed Amen alone before the bass | Christodoulou 2020 (*Dancecult*) on "Serenity"; DOA 2024 | **82%** of drops: the break keeps running while the low end falls **19 dB** — but for a median **1.2 bars**, not 4-8 | **Confirmed in kind, shorter in length** |
| Signal the drop with a snare roll, a riser, or silence | tutorials; modern DnB lore | rolls before **27%**; risers **0 of 22**; gaps before **27%**, median **80 ms** (one 16th) | **Contradicted** |
| Breakdowns: pads, strings, atmosphere, a lull | Reynolds 1994-95; DJ Mag 2018 | breakdowns get **brighter and busier**, only 1.3 dB quieter; **5** sustained sounds in 21 minutes | **Contradicted for this set** |

### Breaks and kicks

| archetype | who says it | measured | verdict |
|---|---|---|---|
| Breaks cut to fragments and rebuilt, never looped | Reynolds; Chapman (via Christodoulou) | no bar ever repeats exactly; 4.6 ms of microtiming between "identical" bars | **Confirmed** |
| Jungle is sequenced, and not ashamed of it | Omni Trio, in James' *State of Bass* 1997 | quantised placement (8th positions within 7.5 ms), human content | **Confirmed** |
| Swung, shuffled breaks | tutorials (50-60% swing); a profile of Tim Reaper | **52.4%**: straight | **Contradicted** |
| The revival refuses two-step | DJ Mag 2018; DJ Storm 2018 | break kick **58%**, two-step **13%** | **Confirmed** |
| Two-step as the default beat | DnB forum lore | 13% of runtime, in the most loop-like record | **Contradicted for jungle** |
| A high-passed break layered over the main one carries the 16ths | Attack 2023 (high-pass at 214 Hz); forums (150-250 Hz) | a 16th carrier in **~70-75%** of bars, cut at **80-320 Hz**; the full break stacks under it at drops | **Confirmed** |
| The 4-bar pattern as the unit | tracker patterns: 64 rows = 4 bars of 16ths | lag-4 similarity 0.486; fills and density cycle on 4 bars | **Confirmed** — this explains the group returning, not why neighbouring bars differ |

### Bass

| archetype | who says it | measured | verdict |
|---|---|---|---|
| Jungle bass is the reese | press histories; Qobuz 2026, of Tim Reaper | a **clean sub**: 2nd harmonic −16.6 dB, 65% of power below 60 Hz | **Contradicted in this set** (a reese in the mids, or on his own records, would not show here) |
| A pure sine or 808 sub | Beatportal 2020; tutorials; forums | peak at **40-50 Hz**, a sine-like tone | **Confirmed** |
| The 808 kick *is* the sub, which is where the "boom" comes from | tutorials; forums; the Reaper profile | every note starts **+30 st** high and falls with a **12 ms** time constant. A stock 808's pitch jump lasts ~6 ms and doesn't fit; a sampler sine with a pitch envelope (the S950's WARP, the S1000's envelope-to-pitch) fits better, and the slow +1 st tail matches the 808's own sag | **Nuanced** |
| Sidechain the bass 3-6 dB under the kick | the forum majority (~10 threads, nearly all DnB); modern tutorials | duck **−0.5 dB**; the sub even rises +2.3 dB at the kick | **Contradicted** |
| Separate kick and sub by EQ and register instead | a forum minority; mono sampler outputs | kick body **60-250 Hz**, sub below 60 | **Confirmed** |
| A half-time dub bassline of long sliding notes | press; tutorials | right about the *rate* (a note ~once a beat, a pitch change ~once a bar), wrong about the *shape*: median note **0.6 beats**, never held past 1.4 bars. Half the "glides" are the onset drop smeared by the tracker; the rest go up and down equally | **Nuanced** |
| The bass lands regularly and gives the track its structure | Christodoulou on Lemon D's "This Is L.A." | riffs loop at 2/4/8 bars, hold a median **11 bars**, and change on 8-bar lines 33% of the time (chance 19%) | **Confirmed** |

### Hooks and space

| archetype | who says it | measured | verdict |
|---|---|---|---|
| Atmospheres: pads, divas, long dub echo | Reynolds 1994-95; DJ Mag 2018 | 5 sustained sounds; no delay at 1/4 or longer (delays of 120, 181 and 45 ms) | **Contradicted for this set** (a delay at 1/4 or longer is partly a detection limit) |
| How much hook is too much? | nobody gives a number | **39%** of bars, median **1.2 beats**, fundamentals **233-392 Hz** | **The set supplies the number** |
| A mono low end, with effects sent per hit | mono sampler outputs; per-hit sends | nothing below 150 Hz in the sides; stereo movement follows events, not a cycle | **Confirmed** |

## What the discourse gets right

- **Pressure, not arcs.** The tune is a plateau with the bass as the event, not a story with a
  climax. Reynolds heard it in 1996; the set is full 86% of the time, with no risers at all.
- **Subtraction is the drop.** The academic account of a high-passed Amen playing alone before the
  lows come in is almost exactly the measured device.
- **Change on a schedule, in layers.** The forum rule of thumb — something every 8 bars, something
  bigger at 16 or 32 — matches the measured layer clocks nearly number for number.
- **Chopped, sequenced, never looped.** Breaks rebuilt from fragments on a quantised grid.
- **The revival is break-driven**, not two-step, and a high-passed break carries the 16ths.
- **The sub is clean**, and kick and sub share the room by register.

## What it gets wrong, and why

- **DnB lore projected back onto jungle.** Sidechaining, two-step as the default, and the reese as
  "the" bass all describe mid-90s techstep and modern DnB better than this set.
- **Tutorials describe a standalone track, not a DJ set.** Long builds, breakdowns and 8-bar
  drop-outs are what a record needs to stand on its own; in a set, the DJ cuts most of them out.
- **The EDM build is assumed.** Risers, rolls and silence before the drop are near-universal in
  modern guides, and almost absent here.
- **Atmospheric jungle stands in for the whole genre.** Pads and long dub echoes are part of the
  story the press tells, not part of this set.
- **"Three bars and a fill" is a pop and hip-hop habit**, not a jungle one — nobody in the jungle
  discourse says it, and the music does the opposite.

## What nobody says, and only the measurement shows

- The bass **isn't ducked**. No revival source mentions sidechaining at all.
- **Every sub note starts with a deep, fast pitch drop** (+30 st, settling in 12 ms), strong in
  some records and absent in others.
- **Hooks sit low, at 233-392 Hz**, above a 10 dB valley at 233 Hz that separates them from the bass.
- **The layers are nested**: the riff sets the clock, and the kick, carrier and sub tone change on
  riff changes; three or four layers turning over together marks a real section change.
- **Neighbouring bars are as unalike as random ones**, while the 4-bar group returns.
- **A drop bar has fewer onsets than a groove bar**, and breakdowns are the busier state.
- **How the DJ joins records**: hard cuts of 1-5 bars prepared by removing the bass, or blends of
  8-32 bars, and nothing in between.

## What no source explains

- Why consecutive bars differ as much as random pairs (tracker patterns explain the 4-bar return,
  not this).
- When sidechaining and risers entered drum & bass.
- The specific delay times (120, 181, 45 ms).
- Why hooks sit at 233-392 Hz.
- The key of E♭ minor.

## Caveats

- **A DJ set is not a record.** Some subtraction drops may be the DJ's bass EQ rather than the
  records, and breakdowns may be missing because the DJ cut them. The measurement can't separate the
  two.
- **A 2026 revival set is not 1994.** Where a golden-era archetype fails here, it may still describe
  its own era.
- **Access was limited.** Reddit opts out of Anthropic's crawler and was not routed around. Dogs On
  Acid, Gearspace and Discogs returned errors, so those claims rest on search snippets. The session's
  shared 200-search budget ran out before FACT, Vice and lectures by Photek, Doc Scott, Hype, Bukem,
  Dillinja or Remarc could be reached.
- **Some results rest on small numbers.** The still bass under a two-step comes from 3 sections, and
  none of the set's 9 records is identified, so how many are Tim Reaper's own is unknown.

## The archetype both sides agree on

Where the discourse and the measurement point the same way, the minimal jungle tune is:

- a **clean sine sub** with a fast pitch drop on each note, separated from the kick by register,
  not ducked
- a **high-passed break carrying the 16ths**, with the full break underneath when it drops
- drops made by **taking the low end away for about a bar** while the break keeps running — no
  riser
- a **riff that changes about every 8 bars**, a sub tone about every 16, and drums about every 32,
  with the slow changes landing where the riff changes
- bars that **differ from each other inside a 4-bar group** that returns
- **short hooks** in the low mids, in about 3 bars out of every 8
