# Jungle scene rules (working rules for the Live set, 2026-09-16)

How this session is built, agreed with the user after measuring the Tim Reaper reference
([2026-09-16_reaper/](2026-09-16_reaper/README.md)) and checking it against the jungle discourse
([archetypes.md](2026-09-16_reaper/archetypes.md)). Tempo 170 (faster than the reference's 166, by
choice). Key F# minor, fundamental F#0 (46.25 Hz).

## A scene is a section

A scene in Live is a section of a record. Its identity is set once per scene and held there:

- **the spine voice**: what instruments and effects play the spine
- **its signature hits**: 2-4 extra positions that land in most of its bars
- **its kick style**: break kick, sparse or syncopated, two-step (rarely); never four-on-the-floor
- **its 16th carrier**: a high-passed break or short percussion playing the 16ths
- **its sub**: tone, pitch-drop attack, bassline

In the reference, kick style holds a median 28 bars and the carrier 32. When a real section changes,
3-4 of these layers turn over on the same bar.

## The spine

**Kick on 1, snares on 2 and 4**, and usually a second kick on the "and" of 3. The positions are
required and prominent in every scene; the reference hits them in 91%, 94% and 89% of all bars, and 66%
for the "and" of 3.

**What changes per scene is the sound on the spine, not where it sits**: different percussive
instruments, with different effects on them. The spine gets its own lane so each scene can give it
its own voice, since effects live on tracks, not clips.

## Signature hits

Beyond the spine, each reference section has a few positions that land in 80-100% of its bars, and
they differ between records. Beat 3 alone ranges from empty (6%) to certain (100%). Density runs
22-28.5 hits a bar. Examples from the reference: the "and" of 3 plus the "and" and "a" of 2; beat 3
plus the "and" of 4; the "e" of 2 plus the "a" of 4; the "a" of 2 plus the "e" of 4.

## The chop

Breaks are built from slices that vary in six ways:

| dimension | means | done with |
|---|---|---|
| position | where the slice starts, re-dealt on the 16ths | note start |
| length | how much of the slice plays | note length (pads are gated) |
| pitch | the slice transposed | variant pads with Transpose |
| repetition | stutters and rolls | repeated notes; start-offset variant pads |
| stretch | the slice slowed, with sampler-style artefacts | pre-rendered stretched variant pads |
| reversal | the slice played backwards | pre-rendered reversed variant pads |

## How often things change

| clock | what changes |
|---|---|
| every bar | the in-between hits are re-dealt (about 15 of 48 hit slots change from bar to bar; neighbouring bars are no more alike than random ones) |
| every 4 bars | the group comes back similar, not identical (lag-4 similarity 0.486); fills land on this line about 1 opportunity in 4 (6.5% of bars) |
| every scene | the identity above |

The spine never changes inside a scene, and nothing is ever a literal loop.

## In-scene variation is chance

**Variation inside a scene comes from each hit's chance (Live's per-note probability), not from
writing out more bars.** A scene's clip holds its distribution:

- spine hits at 100%
- signature hits high (80-100%)
- the other 8th positions around the reference's ~67%
- the "e" and "a" 16ths low (~34%)
- a fill at low chance on the last bar of the 4-bar group, so it lands about 1 time in 4

Every pass through the loop deals a fresh bar from the same distribution, which is what the reference
does.

## The bass

- a clean sine sub; each note starts with a fast pitch drop (+30 st, settling in ~12 ms); no sidechain
- kick and sub separated by register (kick body 60-250 Hz, sub below 60)
- notes struck at the front of the bar; mostly repeats and steps; about one pitch change a bar
- loops of 4 bars (39% of the time) or 8 (31%), repeating 8-16 bars before they change
- short notes (a 16th to an 8th) are common, but notes start about a beat apart - no "8ths all over it"
- phrases drop to a low "dum" on the fundamental and leave a gap. The break's level is unchanged while
  the low end falls ~6 dB, so the break stands out there. About one phrase in two or three ends that way.
