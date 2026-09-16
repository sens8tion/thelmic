# Jungle archetypes in forum lore, checked against the Reaper set

What producer and listener forums say are the "rules" of jungle structure, checked claim by claim
against the measurements in this folder ([README.md](README.md), [alignment.md](alignment.md) and
the seven reports). Gathered 2026-09-16 from 9 forums and about 115 threads. Everything is
paraphrased. Text in quotation marks is a slogan or label, not verbatim forum text.

**How to read it**

- **Seen**: **F** means the thread was fetched. **S** means snippet only: a search engine's summary
  of the page, not the page itself. S rows are weaker. The engine often blends several threads into
  one summary, so a claim is pinned to a thread only where a narrow search on that thread's exact
  title returned it; otherwise the row says *cluster*. Fetched pages also passed through a
  summarising model, so usernames and user counts on F rows are approximate too.
- **Held by**: *1 user*, *several* (in one thread), or *recurring* with the number of separate
  threads. *Contested* means someone in those threads argued the other way.
- **Year**: taken from the page or search metadata. Dogs On Acid years marked `~` are estimated
  from the thread ID, anchored on four dated threads (565479 = 2008, 644729 = Sept 2009,
  765121 = Oct 2014, 827212 = Oct 2024). Treat them as ±2 years.
- **Verdict**: CONFIRMED / CONTRADICTED / NUANCED / NOT MEASURABLE, followed by the number that
  decides it.
- **Scope tags**: the measurement is a 21-minute section of one DJ's set: Tim Reaper, 166 BPM,
  9 records. Most forum lore is about *writing a track*, and much of it is about *DnB* or generic
  EDM, not jungle. **[track]** and **[DnB]** mark advice aimed at a different object than the one
  measured. For those rows the verdict says what the set shows, not whether the advice fails at its
  own job.

---

## 1. Claims

Source codes like `[DOA 20]` point to section 3.

### 1.1 Arrangement and DJ phrasing

| # | claim (paraphrased) | sources | held by | seen | verdict and the number |
|---|---|---|---|---|---|
| A1 | **[track]** The DJ-friendly template: intro 32-64 bars (range quoted 16-144), a 16-bar build, first drop 32-96, breakdown 16-32, second drop, outro 16-64. Comes to about 5:45 at 170 BPM. | [DOA 1] 2014, [DOA 2] ~2024, [DOA 3] ~2008, [GS 1] ~2023, [DNBF 1], [DNBF 2], [ABL 1] 2008 (generic dance), [GS 3] (EDM, unconfirmed) | recurring, 8 threads on 5 forums, 2008-2024. Usually posted alongside a caveat that the classics ignore it. | S (F for ABL 1) | **NUANCED.** A DJ set cannot show a whole record's intro. It does show the DJ playing 40-192 bars of each record (130/46/130/72/40/192/133/64/64), with drops a median 33.5 bars apart. The 32-bar grain holds. The neat 64-bar drop block does not show up: full-energy runs last a median 12.4 bars between reductions. |
| A2 | Intros, outros and sections come in 8s (4/8/16/32) so DJs can mix. DnB can't be faded in like techno: the incoming tune's next section has to land on an 8- or 16-bar line. One producer starts breaks 2 bars early on purpose. | [DOA 5] ~2017, [DOA 3], [KVR 1] 2005, [GS 2] (unconfirmed) | recurring, 4 threads; contested by 1 | S / F | **CONFIRMED.** Phrasing is strictly 4-bar (100% of sections within 2 bars of a multiple of 4) and loosely 8-bar (84%). Lag-8 is the strongest period (excess +0.181). Five of nine record blocks are exact multiples of 8 and the rest are within 3 bars. 86% of drop intervals land on whole bars. |
| A3 | Keep the defined bass (and busy leads) out of the first 32 bars so DJs can mix. Counter-example from the same thread: Remarc's *R.I.P.* brings bass in around 40 s. | [KVR 1] 2005, [GS 1] ~2023 | 2 threads, 1 counter-example | F / S | **CONFIRMED, as the DJ uses it.** Bass is the handover channel. 17% of bars sit below 5% low-band energy, and 5 of the 9 bass-less runs of 4+ bars (34, 5, 8, 7, 15 bars) sit on a record seam. The set opens with 34 bass-less bars. Away from the seams it never goes more than 5 bars without sub. |
| A4 | Modern jungle intros are short, about 16 bars, often with vocals from bar 1. One DJ misses 60-90 s overlaps and loops intros in Serato to stretch them. | [DOA 4] ~2022 | 1 original post, replies with workarounds | S | **CONFIRMED.** Handovers are short. 5 of 8 seams are hard cuts of 1-5 bars (1.4-7.2 s). The longest blend is about 32 bars (46 s), still under the 60-90 s the poster misses. |
| A5 | **[track]** Change something every 8 bars, bigger things at 16/32/64, and in different parts of the sound, not everything at once. | [DOA 6] ~2020 and [DOA 7] ~2025 (cluster), [KVR 1] 2005 | recurring, 3 | S / F | **CONFIRMED, closely.** Each layer keeps its own clock: riff about every 8 bars, sub tone 17, kick pattern 28, 16th carrier 32. The refinement: slow layers change *where the riff changes*. 77% of kick changes land on a riff change, against 21% by chance, and 3-4 layers turn over together 8x more often than chance. |
| A6 | **[track]** Build a 16-bar loop from a 4-bar one: double it and alter it, then double and alter again. Add small turnarounds every 2, 4 and 8 bars. In a house thread, one user varies the loop every 4 bars and another says 2-bar changes go stale. | [DOA 6] ~2020, [ABL 2] 2006, [KVR 3] 2012 (house) | 3 threads; the 2-bar rate is contested | S / F | **CONFIRMED at 4, weak at 2.** The most common best-repeat lag is 4 bars (39% of bars), with lag-4 similarity 0.486. Fills and onset density cycle on 4 bars (autocorrelation +0.19 and +0.20). The 2-bar excess is only +0.061. |
| A7 | **[track]** Fewer elements sound bigger. Pro DnB arrangements are minimal, with each sound in its own frequency slot. Dissent: that sounds clinical; not every part needs to be powerful. | [KVR 4] 2013, [KVR 5] 2021 | 2 threads, about 5 users; 2 dissent | F | **CONFIRMED.** A drop bar has *fewer* events than a groove bar: 21 band-onsets against 32, about 1.8 bands per sixteenth. Register slots are explicit: kick at 60-250 Hz, sub below 60 Hz, a 10 dB valley at 233 Hz, hooks above it. |
| A8 | Rollers roll along on ghosts and fills with few switches, adding detail as they go. Steppers are rigid two-steps with space. "Rollers" now often just means a one-note bassline. The label is argued over, and some call it meaningless. | [DOA 8] ~2018, [DOA 9] ~2012, [DOA 10] ~2017 | recurring, 3; contested | S | **NOT MEASURABLE as a label.** On both readings this set is no roller. Consecutive bars are the least alike pair (lag-1 0.355). The bass moves 0.90 times a bar and never drones. It does "roll" in the looser sense of staying full for 86% of its runtime. |
| A9 | **[track]** Do we still need 32-64 bar intros and 32-bar breakdowns with modern DJ tools, or were they a vinyl convenience? | [DOA 11] ~2012 | 1 user asking; contested | S | **NUANCED.** This DJ mostly cuts rather than blends (5 cuts to 3 blends), so long intros are rarely used as blend time. They are used as *places to cut into*: one seam cuts straight into a new record's 16 bass-less bars. |
| A10 | Breakdowns should be sparse, like stepping out of the club, then snap back to full. Ping-pong delay on the lead before big transitions. | [ELK 1] p13, 2024 | 1 user | F | **CONTRADICTED.** Breakdowns here are *brighter and busier*: only 1.3 dB quieter, centroid +277 Hz, and onset density rises in 64% of them. Delays are short (1/8 triplet ~120 ms, 1/8 ~181 ms, 45 ms slap), with nothing at 1/4 or longer. |
| A11 | Second drops: usually made different (a new bassline, one element added or removed). Others say most are copy-pastes of the first and pointless. DJs value them as a second chance to double-drop or switch. | [DOA 12] ~2008, [DOA 13] ~2008 | recurring, 2; contested | S | **NOT MEASURABLE per record.** No record comes back, and seams hide which drop is which. Related: inside a record, the median section is 20% new material with a 40-84% verbatim return, and the riff turns over every ~8 bars. "The same again with something changed" is how the records work at every scale. |
| A12 | Double drops: two tunes drop together at full volume. It needs tight sync, compatible keys, and knowing both records' bar counts. | [DOA 13] ~2008, [DOA 14] ~2009, [DOA 15] ~2016 | recurring, 3 | S | **CONFIRMED.** The whole set runs on one master clock (four estimates agree within 0.03 BPM). 84.6% of bass time across 9 records sits inside E-flat minor. There is one long double-play (bars 592-630, ~46 s). The one doubled-drum handover (bar 418: 2 bars at 1.9x the onset norm, then the drop) is signalled by density, not by a riser. |
| A13 | Switching basslines: during a double drop, cut between the two records' bass instead of EQing the lows back and forth. It works when the lines differ clearly and share a key. Cited remixes swap basslines every 4 bars. | [DOA 16] ~2006 | several | S | **CONFIRMED.** In the bars 592-630 double-play, the low band lurches 0.4% -> 21% -> 1.0% over three bars as the records alternate bar by bar. |

### 1.2 Break edits and fills

| # | claim (paraphrased) | sources | held by | seen | verdict and the number |
|---|---|---|---|---|---|
| E1 | **[track]** Arrange edits by copying and altering: make a variation, copy it and change it, then copy the pair and change the second half, and so on. The breaks keep evolving but the arrangement stays simple. | [DOA 17] ~2008, [DOA 18] ~2017 | recurring (2-3 hits, probably one widely echoed post) | S | **CONFIRMED.** Nothing is looped: even pattern-identical bars differ by 4.6 ms of microtiming, where a loop gives 0-1 ms. Bar N still resembles bar N+4 (0.486) more than bar N+1 (0.355), which is what copy-and-alter produces. |
| E2 | Most producers just loop one bar of the Amen, though four bars are available. Better to build a repeating drum-edit hook you could almost hum. | [DOA 17] | 1 user (complaining about others) | S | **CONTRADICTED on the looping, CONFIRMED on the hook.** Lag-1 similarity equals the random baseline, so there are no one-bar loops. The hummable hook is the 4-bar group that returns. |
| E3 | Drums should read like sentences, or an MC's bars. Wacky edit after wacky edit sounds bad; audition 4, 8 or 16 bars, not one bar on repeat. Too much variety kills the groove. Changing randomly every bar is a classic beginner mistake. | [DOA 17], [DOA 18], [KVR 1] 2005, [REN 10] (earlier brief) | recurring, 4 | S / F | **CONFIRMED.** Fills are 6.5% of bars (one every 15.5) and only 1.23x denser than a normal bar. About 15 of 48 cells change between adjacent bars: every bar differs, and none is wild. |
| E4 | Keep 1-2 elements fairly steady (kick and main snare, or straight hats) and vary the rest by rolling, retriggering, pitching and reversing. Build 2-3 core patterns and repeat them as frames. Change always, but planned, never random. | [ELK 3] 2016 and p4 2018 | several (3 users over 2 years) | F | **NUANCED, mostly backed.** The snare is nearly fixed: slots 4 and 12 are occupied 0.94 and 0.89 of the time. The kick moves: slot 0 is 0.91 but slot 10 only 0.66. The *low* band defines the 4-bar unit and the high band re-chops (lag-4 excess: low +0.137, high +0.116; at lag 1 every band is within ±0.03 of zero). |
| E5 | Old jungle beats are identical phrases in 1-4 bar loops. The core trick: retrigger the loop on step 7 of 16 so the first chunk repeats (Dillinja cited). Over-chopping loses the loop's feel. | [GS 4] ~2014 | ≥1 user | S | **CONTRADICTED on "identical", NOT MEASURABLE on the retrigger.** Identical bars would put lag-1 similarity near 1; it sits at the random baseline, and pattern-identical bars still differ by 4.6 ms. The within-bar retrigger can't be tested: the chop-detection test failed its own selection-bias control. |
| E6 | Slice in longer chunks (8th-note blocks, or snare-hat-hat phrases), not single 16th hits. Transient slicing loses the rolling feel. Against: most producers slice to 16ths and rearrange. | For chunks: [REN 1] 2014, [ELK 2] 2020. For 16ths: [KVR 11] 2007, [ELK 2] (1 dissenter) | contested across forums, about 4 vs 5 users | F | **NUANCED, leaning chunks.** Placement on 8ths is tight (7.5 ms spread) while odd 16ths wander (13.5 ms): quantised placement, human content inside the chunk. That fits 8th-note blocks that keep the break's own timing. Slice length itself is not measured. |
| E7 | Keep the break's micro-timing, because all-on-grid sounds mechanical. Program slowly, pitch up and layer. MIDI breaks sound lifeless at 150+ BPM. Rebuttal: short hits with varied velocity work. | [KVR 7] 2010, [KVR 10] 2005 | 2 threads, 3 users vs 1 | F | **CONFIRMED.** Straight but not rigid: a drift-tracked grid puts 76.6% of onsets within 10 ms, where a rigid grid manages 35.1%. |
| E8 | A jungle/DnB fill is a few 8th-note hits with straight 16ths filling the rest. Simple fills land better at speed. A fill rewards attention by breaking the pattern without losing the groove. Move it from bar 8 to bar 7, or to bar 1 of the next phrase. Elsewhere, one user wants more snare fills and another fewer. | [DOA 19] ~2023, [ABL 2] 2006 | several; the amount is contested | S / F | **NUANCED, mostly backed.** Fills sit on a 4-bar cycle (autocorrelation +0.19 at lag 4, the peak out to 32) but take only about one slot in four. They avoid the last bar: the strongest 4-bar position is 3 (8.5%) and the strongest 8-bar position is 2 (10.2%). On amount, the "fewer" side wins (6.5% of bars). |
| E9 | "Three bars and a fill": repeat three bars, disturb the fourth. | **Not found as a rule on any forum reached.** Neither the DOA, KVR nor Gearspace searches turned up a numbered fill rule. The nearest wording is a teaching page on dancehall and hip-hop form, not a forum: drop layers in each fourth bar [WEB 1]. | not found | F (WEB 1) | **CONTRADICTED.** Tested directly: the spread across the four bar positions is 0.042 (p = 0.20). The music runs A-B-C-D with the group returning. The idea is a pop/hip-hop arranging habit, not jungle forum lore. |
| E10 | The shuffle is a closed hat on the off-beat plus a ghost snare on the next 16th. The DnB feel comes from ghost snares and velocity-shuffled 16th hats. Think in 16ths, but not straight ones. | [DOA 18] ~2017, [KVR 18] 2008, [ABL 8] 2008 | recurring, 3 threads, about 7 users | S / F | **NUANCED.** The shuffle is *occupancy and level*, not timing. Odd 16ths are hit only 0.34 of the time, against 0.67 for even off-beats. Timing is essentially straight: 52.4% swing, a 4 ms lean. |
| E11 | Vary repeated snares by texture (filter, pitch, transient shape), not just volume. The pitched tonal snare is overused. | [KVR 9] 2022, [KVR 17] 2017 | 2 threads | F | **NOT MEASURABLE** with structure-only features. |

### 1.3 Drops and builds

| # | claim (paraphrased) | sources | held by | seen | verdict and the number |
|---|---|---|---|---|---|
| D1 | **[track]** Build for 32 bars adding drum parts and themes, then drop most elements for 8 bars so the DJ knows the drop is coming. Don't bring the Amen in before bar 17; earlier is too aggressive. | [DOA 20] 2024 | 1-2 users | S | **NUANCED: right direction, wrong size.** 82% of drops are set up by subtraction, but only the low end comes out (a median 19 dB) while the break keeps full onset density. The absence is short: median 1.2 bars, with 4+ bars in only 23% of drops. |
| D2 | **[track]** Build-up kit: risers, white-noise whooshes, fills, film samples, kick rolls, quarter-note hats, filter sweeps. Cut the lows during the build so the bass hits on the drop. Silence before the drop adds impact. Ride the master up 3 dB through the build. Some members call all this cheat codes that can sound cheap. | [DOA 21] ~2017 | several; contested | S | **Split.** Low-cut build **CONFIRMED** (82%, median 19 dB). Risers **CONTRADICTED** (0 of 22). Rolls 27%, sweeps 23%, stabs 18%: each a minority device. Master ride **CONTRADICTED**: drops are approached by *falling* level, and the drop adds only +2.6 dB RMS. Silence: see D5. |
| D3 | Risers and noise sweeps are a cliché; the kick-roll + riser + filter-sweep drop is an old formula; reverse-reverb risers are worn out. Other threads from the same years ask where to buy riser packs. | [DOA 22] ~2008, [DOA 23] ~2011, [DOA 24] ~2014, [ABL 4] 2010, [KVR 26] 2012 | recurring, 5 threads; contested | S / F | **CONFIRMED.** Zero risers or reverse swells in 22 drops. |
| D4 | **[DnB]** A proper drop needs a stash of risers, downers, reverses and impacts, plus a filter on the drum bus. EDM shape: intro, riser/break, silence, drop. | [DOA 2] ~2024, [KVR 2] 2014 | 2 threads, several users; 1 dissent in each | S / F | **CONTRADICTED for this jungle set.** Risers 0%. The break's high-pass does not open at the drop: openings and closings are equally common and the median corner is unchanged. The drop is +10 dB of sub with the centroid *falling* 394 Hz. |
| D5 | Cut everything for a whole bar, then drop. Silence before a drop increases impact. | [ABL 4] 2010 (prog house), [DOA 21] ~2017, [KVR 2] 2014 | recurring, 3 | F / S | **CONTRADICTED.** Only 27% of drops have a gap at all, and its median is 80 ms, one 16th. The drop is paid for by the missing low end, not by silence. |
| D6 | **[track]** Write the drop first, then build the lead-in by subtracting from it. | [ABL 4] 2010 (prog house) | 1 user | F | **CONFIRMED.** 82% of drops are subtraction alone, and there's no layered build-in afterwards: bar 2 is within 0.5 dB of bar 1 and onset counts are flat. |
| D7 | Snare-roll builds: the classic ramp (16ths into 32nds with rising volume) against the view that they are tired and irritating. Techniques: retrigger with a pitch LFO; play rolls melodically across keys. | [ELK 5] 2024, [ELK 4] p2 2015, [GS 4] ~2014 | 3 threads; contested | F / S | **NUANCED.** Rolls lead into 27% of drops: alive, but a minority device, never the default. |
| D8 | A drop is a sudden switch to a new bassline or motif and a change of pace. | [KVR 2] 2014 | 3 users, 1 disputes the definition | F | **NUANCED.** New bass, yes: sub +10 dB, bass +5 dB. Change of pace, no: onset density moves a median +0.2 per bar, and mid and high actually fall 0.9 and 1.1 dB. It's a re-weighting, not a lift. |

### 1.4 Bass

| # | claim (paraphrased) | sources | held by | seen | verdict and the number |
|---|---|---|---|---|---|
| B1 | **[DnB]** Sidechain the bass to the kick: 3-6 dB of reduction, sometimes keyed from the snare too. It's near-essential without a mixing desk. Sidechaining the sub to kick and snare is fashionable. Duck the reese from the kick. Modern DnB sidechains to both kick and snare; it's more common now than in the early 2000s, and the new jungle wave credits it. Rob Swire (Pendulum) is named as an early adopter. | [DOA 25] 2008, [DOA 26] 2017, [DOA 29] ~2022, [DOA 51] (cluster), [KVR 5] 2021, [KVR 8] 2015, [KVR 22] 2017, [REN 5] 2007, [REN 4] 2015 (1 user), [GS 8] ~2023 (a little, only if needed) | recurring, about 10 threads, mostly DnB or generic | S / F | **CONTRADICTED.** The duck under the kick measures −0.5 dB. Against a kick-free baseline the sub *rises* +2.3 dB at the kick. None of 14 measurable sections ducks past 4 dB. |
| B2 | Don't sidechain, or barely. EQ kick and bass so their peaks don't collide. Many commercial tracks use none. With the kick ~30 Hz above the sub it isn't needed; if used, go gentle and sub-only. Ducking breaks makes them sound wrapped around the kick; slice them to fit instead. Old-school jungle sidechained sounds ornamental. Dom & Roland reportedly avoid it so the kick varies hit to hit (second-hand). The old-jungle bass threads never mention sidechain at all. | [DOA 25] (dissenters), [DOA 27] ~2023, [DOA 28] ~2007, [KVR 23] 2007, [REN 4] 2015, [ABL 6] 2016, [ABL 7] 2009, [KVR 19]/[KVR 20] (by silence) | recurring, about 8 threads | S / F | **CONFIRMED.** Kick and bass separate by **register**. The kick puts 42.5% of its energy in 60-250 Hz, against the bass's 16.5%. The bass owns below 60 Hz (73.8% vs 50.8%) and peaks at 40-50 Hz. ABL 7's rule of thumb (kick 80-90 Hz, bass at 60 or below) matches almost exactly. |
| B3 | The classic jungle bass was a resampled 808 kick, or the sampler's built-in sine (S950/S1000), or Jungle Warfare 808s, often overdriven on the desk. Cheap samplers' aliasing helped it cut. Also DX7 bass transposed down. A sampled 808 gives punchier, shorter high notes than plugins. | [KVR 19] 2008, [REN 1] 2014, [DOA 30] ~2017, [DOA 32] ~2019, [ELK 4] 2015, [KVR 20] 2007, [GS 9] ~2016, [GS 10] ~2021 | recurring, 8 threads on 5 forums; no dissent | F / S | **CONFIRMED.** Every bass note starts with a pitch drop, 808-style, and the shape varies by record. The sub is clean: the fundamental sits 16.6 dB above the 2nd harmonic. |
| B4 | Pitch-envelope depth. One camp: it falls only slightly and settles quickly, a sine with slight pitch modulation. The other: a fast envelope from about 2 octaves up. A jungle drop bass is a sine plus square with a pitch envelope. | slight: [DOA 31] ~2020, [DOA 30], [KVR 19]. 2 octaves: [GS 8] ~2023. [ABL 5] 2005 | recurring, 5 threads; the depth is contested | S / F | **CONFIRMED on speed; on depth, the deep camp is right.** The drop is about +30 semitones (2.5 octaves), but with a 12 ms time constant. That's heard as the attack, not a slide, which is why half the forum hears it as slight. |
| B5 | The 808 wants a long decay, the "boom", and very simple patterns. | [DOA 30] ~2017, [GS 8] ~2023 | 2 threads | S | **NUANCED: simple yes, long no.** Median note 0.60 beats, only 0.7% of notes over a bar, nothing held past 1.4 bars, 0.90 changes per bar. The line is simple: 34.6% of intervals are repeats and 28.5% steps of 1-2 semitones. |
| B6 | Jungle is about the sub, not the reese. Reese belongs to the techstep/DnB line (Alex Reece, No U-Turn). Jungle/DnB bass is detuned, distorted and filtered. Modern jungle uses both 808s and reeses. | not reese: [KVR 19] 2008, [REN 3] p2. Reese/detune: [DOA 35] ~2015, [DOA 36] ~2014, [KVR 19] (1 user), [KVR 21] 2006. Both: [GS 8] | recurring, 6 threads; contested | F / S | **CONFIRMED for the sub.** Clean sub, 65.6% of power below 60 Hz. A reese would push harmonics 2-8 close to the fundamental; here h1 leads h2 by 16.6 dB. The variants that do occur are clipped or octave-doubled subs, not reeses. |
| B7 | Classic jungle is reggae basslines at half the break tempo (about 80 over 160): roots and fifths, pentatonic, rhythm first, few notes. Write it on one note, then add pitch. | [KVR 19] 2008 (2-3 users), [REN 1] 2014, [DOA 33] ~2020, [DOA 34] ~2020, [DOA 35] ~2015 | recurring, 5 threads on 3 forums; no dissent | F / S | **NUANCED.** The harmonic rhythm is roughly half-time (about one change per bar, two per half-time bar), but the articulation is short (median 0.60 beats) and the vocabulary is steps, not roots and fifths: repeats 34.6%, 1-2 semitone steps 28.5%, fifths 7.4%, octaves 1.8%. In 2-bar riffs the second bar sits about a semitone lower in two cycles out of three. |
| B8 | Deep downward glides (glissandos) for the sub: mono, glide on, overlap notes to bend down. The "swell" bass is played legato. | [REN 3] 2009, [DOA 34] ~2020, [KVR 21] 2006 | recurring, 3 | F / S | **NUANCED: common, but shallow.** 41% of transitions are portamento (2.5 glide runs a bar, 59% falling), but the median glide is 96 ms over 0.76 semitones, not a deep glissando. |
| B9 | Centre the sub near 50 Hz with the kick above it (kick 80-90 Hz, bass at 60 or below). Keep sub and kick mono and centred. | [REN 3] 2009, [ABL 7] 2009, [ABL 6] 2016, [REN 5] 2007 | recurring, 4 | F | **CONFIRMED.** The sub peaks at 40-50 Hz. Side energy below 150 Hz sits 33 dB under the mid. |
| B10 | Busy drums eat spectrum and leave less room for a big bass. It's a trade-off. | [SOS 1] 2010 | 2 users | F | **CONFIRMED.** At a drop the sub rises 10 dB while mid (−0.9) and high (−1.1 dB) fall, and the bar gets *fewer* events. |
| B11 | Simple breaks call for a busier bass, and vice versa. | [REN 10] (earlier brief) | 1 thread | F | **CONTRADICTED where testable.** Under the simplest drums, the two-step, the bass barely moves. |
| B12 | Early jungle and DnB could switch scales between parts of a track; modern tunes stick to one theme. | [DOA 29]/[DOA 44] (cluster) | 1 user | S | **NUANCED.** Colour and riff change often (sub tone every ~17 bars, riff every ~8, riffs repeating a median 11 bars), but tonality holds: 84.6% of bass time sits in E-flat minor across 9 records. That's partly the DJ choosing compatible keys. |

### 1.5 Kicks

| # | claim (paraphrased) | sources | held by | seen | verdict and the number |
|---|---|---|---|---|---|
| K1 | Break kick or sample? There's no right answer. Many keep the break's hats and ghosts and use sampled kick and snare, because it's easier to mix. Others reinforce the break's kick with a sine, 808 or 909, or let the break rattle along behind reinforced hits. Bus the kick with the drums for breaks and with the bass for EDM. | [DOA 37] ~2019, [DOA 49] ~2023, [KVR 16] 2007 (3 vs 1), [KVR 9] 2022, [KVR 15] 2015 | recurring, 5; contested | S / F | **NUANCED.** By runtime the break's own kick pattern leads at 58%, then sparse/syncopated 26%, two-step 13%, none 4%. Whether a sample sits under the break kick can't be separated in the measurement. |
| K2 | A 909 under break kicks fails unless phase and timing are perfect; low-passed 808s work better. Layer a second Amen kick pitched down 5-6 semitones, low-passed and gated. 90s DnB was a break tightened with kick, snare and ride. | [GS 5] ~2016, [GS 6] (unconfirmed), [DOA 18]/[DOA 38] (cluster) | 3 threads | S | **NOT MEASURABLE** (the layering isn't separable). Consistent with the kick owning 60-250 Hz. |
| K3 | Jungle and DnB are in 4/4 but not four-on-the-floor. The feel comes from kick placement around fixed backbeat snares. 4x4 DnB is contested, some calling the EDM version awful. The early 90s had hybrid grooves between the two. | [DOA 39] ~2023, [DOA 40] ~2003, [DOA 41] ~2017, [ABL 8] 2008, [REN 7] 2011 | recurring, 5 threads on 3 forums | S / F | **CONFIRMED.** No four-on-the-floor detected. Snares on slots 4 (0.94) and 12 (0.89); the kick on slot 0 (0.91) and slot 10 (0.66), and its placement is part of what moves. |
| K4 | The two-step is the standard skeleton: an Amen with extra layers over kick-on-1-and-11, snares on 5 and 13. | [DOA 18] (cluster), [GS 6] | 2 | S | **CONTRADICTED for this set.** The two-step is only 13% of runtime; the break's own kick pattern is 58%. |

### 1.6 The 16th carrier and layered breaks

| # | claim (paraphrased) | sources | held by | seen | verdict and the number |
|---|---|---|---|---|---|
| C1 | Use one break as the anchor and layer others for character and top end, high-passed. Forum corners vary: about 150 Hz, below the snare fundamental ([GS 5]); ~200 Hz to lose the kick ([GS 7]); ~250 Hz with boosts at 500 Hz and 5 kHz ([ABL 8]); a low cut given as 174, unit unstated ([KVR 17]). At 400-500 Hz a break becomes a hat/shaker loop, the early-2000s commercial DnB move (Pendulum, Shock One, Metrik). 90s records used two or more heavily EQ'd breaks and moved between combinations. | [DOA 33] ~2020, [DOA 38] ~2024, [DOA 49] ~2023 (cluster), [GS 5], [GS 7] (candidate), [ABL 8] 2008, [KVR 17] 2017, [KVR 11] 2007 | recurring, about 8 threads on 4 forums | S / F | **CONFIRMED on the layer, NUANCED on the corner.** A 16th carrier runs in about 70-75% of bars, mostly a break high-passed at **80-320 Hz**. That's the 150-250 Hz jungle advice, not the 400-500 Hz hat-loop version, which is the DnB variant. It changes character about every 32 bars, and its filter does *not* open at the drop. |
| C2 | Glue layered breaks on a bus with gentle 2:1 compression (1-2 dB); phase alignment matters most. A mono Amen is fine, since the S950 and W30 were mono. | [REN 8] 2022, [KVR 11] 2007 (3 vs 1) | 2 threads | F | **NOT MEASURABLE** for the compression. Mono: see S1. |

### 1.7 Hooks, stabs and vocals

| # | claim (paraphrased) | sources | held by | seen | verdict and the number |
|---|---|---|---|---|---|
| H1 | Ragga vocals are core to jungle, but recycling the same classic acapellas helped kill the scene. Look for new vocals, not sample-site rips. | [DOA 42] ~2017, [DOA 43] ~2018 | recurring, 2 | S | **NOT MEASURABLE** (originality). For density: 38 of 287 melodic/vocal events are vocal-like. |
| H2 | **[DnB]** Modern DnB throws lazy soundclash vocal samples on top and cares more about sonics than structure. | [DOA 44] ~2024 | several | S | **NOT MEASURABLE** as a judgment. The set treats vocals as punctuation: hooks in 39% of bars, median event 1.2 beats, 81% under 2 beats. |
| H3 | Ragga shouts: time-stretch them over the beat, or mangle them beyond recognition. | [REN 9] 2011 | 2 users; contested | F | **NOT MEASURABLE.** |
| H4 | Old-skool palette: minor-7th stabs, hoovers, chipmunk vocals, clean sine subs; flanger and phaser only arrive around 1996. Jungle pads are sampled minor-7th chord pads. | [KVR 13] 2008 (about 5 users), [KVR 25] 2008 (about 3) | 2 threads; no dissent | F | **NUANCED.** Stabs, yes: 69 stabs and 39 chord stabs among 287 events. Pads, no: only 5 sustained tones and 4 lead lines in 21 minutes. Clean sub: confirmed (B6). |
| H5 | How much hook or vocal is too much? | **No forum gave a number.** All three searches came back empty on this. | not found | - | **The set supplies the number:** 39% of bars (3.1 in every 8), 12% of runtime, median gap 1.5 bars, fundamentals 233-392 Hz. Only 50 of 128 shapes recur, typically three times, 4-8 bars apart. |

### 1.8 Stereo, reverb and delay

| # | claim (paraphrased) | sources | held by | seen | verdict and the number |
|---|---|---|---|---|---|
| S1 | Keep the low end mono: sub, kick and bass centred. Mono below ~200 Hz (club systems and vinyl), or below 300 Hz. | [DOA 35] ~2015 (300 Hz), [DOA 46] ~2008 and [DOA 50] ~2014 (cluster, 200 Hz), [REN 3] 2009, [REN 5] 2007, [KVR 11] 2007 | recurring, 6 threads; no dissent | S / F | **CONFIRMED, with a corner.** Side energy below 150 Hz sits 33 dB under the mid, and the image opens at 250-500 Hz. "Below ~200 Hz" is the accurate rule; 300 Hz is slightly conservative. |
| S2 | Stereo percussion: pan it 30-35%, or barely at all. Modern DnB drums are too wide and too forward. | [ELK 1] p13 2024 (contested), [DOA 44] ~2024 | 2 threads; contested | F / S | **NUANCED.** The width lives in the mids: 53% of side energy sits at 400 Hz-2 kHz. Highs *narrow* in drops. Movement follows events, not cycles: bar-locked autocorrelation is only 0.13-0.21. |
| S3 | Jungle reverb: little and short, so you don't hear it as reverb. Plate on snares, gated or early-reflection reverb to fatten without a tail, delay for character. Bass never gets heavy sends. | [DOA 45] Sept 2009, [DOA 46]/[DOA 50] (cluster) | recurring, 2-3 | S | **CONFIRMED.** Median T20 is 299 ms. Tails are *constant* rather than long: 2-8 kHz stays within 20 dB of its peak 96% of the time. |
| S4 | **[DnB]** Liquid reverb: a huge, diffuse space with long pre-delay. Put long hall reverb on vocal stabs and FX, and keep the drums fairly dry. | [KVR 24] 2012, [KVR 5] 2021 | 2 threads, 4 users | F | **CONTRADICTED for the long tails, CONFIRMED for dry drums.** T20 299 ms; no delay at 1/4 or longer. |
| S5 | Dub moves: spring-reverb snare throws; a hard-panned duplicate delayed by a fraction of a second; ping-pong delay before transitions. | [KVR 27] 2017, [DOA 46] (cluster), [ELK 1] p13 | 3 threads | F / S | **NUANCED.** The measured delays are all short: 1/8 triplet ~120 ms (about 5x chance), 1/8 ~181 ms, and a 45 ms slapback. Throws and hard-panned duplicates weren't measured separately. |
| S6 | Old-skool jungle had dynamics and headroom, so squashing it is the worst thing you can do; modern DnB is LUFS-obsessed. Against: compression is what makes a sped-up Amen sound right. | [DOA 33] ~2020, [DOA 44] ~2024, [KVR 14] 2005 | 3 threads; contested | S / F | **NUANCED.** Limited to 0.0 dBFS, with only 1.8 dB loudness range inside a drop. Yet the median 50 ms crest is 7.5 dB, so transients survive, and breakdown-to-drop steps are 6.4 dB. |

### 1.9 Old skool vs modern jungle vs DnB

| # | claim (paraphrased) | sources | held by | seen | verdict and the number |
|---|---|---|---|---|---|
| O1 | Most people use "jungle" and "DnB" as synonyms. In the late 90s DnB drums grew more minimal, less broken and more programmed. Today's chopped-Amen revival calls itself "jungle" to stand apart. | [DOA 29] ~2022 (17+ pages), [DOA 47] ~2021, [DISC 1], [REN 3] p2, [GS 11] ~2010 | recurring, 5+ threads; strongly contested | S / F | **CONFIRMED as a description of this set.** It's the chopped-break kind: break kick 58%, two-step 13%, nothing looped. |
| O2 | Jungle is ragga and dancehall over rave breaks, with beat programming ahead of the bass. DnB kept the fast breaks and half-tempo bass, dropped the ragga, and tightened the rhythm. | [GS 11] ~2010, [DISC 1] | 2 threads, several users | S | **NUANCED.** Ragga is present but minor (38 vocal-like events). The bass is not secondary: +10 dB of sub is what a drop *is* here. |
| O3 | In DnB, percussion and bass are integrated; in jungle the bassline sits apart from the percussion. | [DOA 47] ~2021 | 1 user | S | **NUANCED.** Sonically separate, yes: register split, no ducking, and hook placement uncorrelated with the sub (r ≈ 0). Structurally coupled, though: 77% of kick-pattern changes land on a riff change. |
| O4 | Once processed single hits come in, it stops being jungle and becomes DnB. Raw S950 stretch artefacts beat clean polish. Modern jungle packs are over-chopped and over-processed. | [ELK 4] 2015, [ELK 1] p6 2022 and p14 2024 | 3 users, 2 threads | F | **NUANCED.** Not over-chopped: fills are 6.5% of bars and adjacent bars differ by ~15 of 48 cells. The sub, though, is clean, not dirty. |
| O5 | **[DnB]** Modern DnB is buildups and drops followed by a boring break with bass screech: dubstep rebranded. | [DOA 44] ~2024, [DOA 29] (cluster) | several | S | **Not this set.** It is the opposite shape: 0 risers, and the drop is a clean sub re-weighting, not a screech. Breakdowns are brighter and busier than drops. |
| O6 | Start from the Amen and you are nearly done; answered with: that advice is two decades out of date. | [KVR 8] 2015 | 2 vs 1 | F | **NOT MEASURABLE.** Break identity wasn't analysed (structure only, nothing sampled). |
| O7 | The original sound is gone, and today's revival is imitation. Posted under a UKF film featuring Tim Reaper himself. | [DOA 48] ~2021 | several; contested | S | **NOT MEASURABLE.** |

---

## 2. Forum lore the measurements back, overturn, or complicate

### Backed

- **DJs phrase in 4s and 8s, and hand over through the bass.** Strict 4-bar and loose 8-bar
  phrasing. Five of nine bass-less runs sit on seams. The bassline-switching trick shows up as a
  bar-by-bar low-band swap (A2, A3, A12, A13).
- **"Change something every 8, bigger things at 16/32" is almost literally the layer clock**: riff
  8, sub tone 17, kick 28, carrier 32. The forums miss one part: the slow layers wait for the riff
  (A5).
- **Risers are a cliché.** Zero in 22 drops, which settles the argument the forums keep having (D3).
- **The no-sidechain, EQ-first camp.** Separation by register, −0.5 dB duck. One 2009 Ableton post
  has the exact split: kick 80-90 Hz, bass at 60 or below (B2, B9).
- **The 808-derived clean sub, not a reese; mono below ~200 Hz; short, constant reverb** (B3, B6,
  S1, S3).
- **A high-passed break layered over the main one**, and at the jungle corner (150-250 Hz), not the
  DnB hat-loop corner (C1).
- **Restraint in edits.** Copy-and-alter, audition in 4-16 bar context, fewer fills rather than
  more, keep the break's micro-timing (E1, E3, E7, E8).
- **No four-on-the-floor** (K3).

### Overturned

- **The pro-sidechain majority.** It is the most repeated mixing advice in these threads (about 10),
  and it's almost all DnB or generic. None of 14 sections ducks past 4 dB (B1).
- **Build-ups that add: risers, rising master, a bar of silence, "drop most things for 8 bars".**
  Drops are approached by falling level. The gap is a median 80 ms. The low end is out a median 1.2
  bars. The break never stops (D1, D2, D4, D5).
- **"Three bars and a fill".** Not even forum lore: no jungle thread states it, and the set runs
  A-B-C-D (p = 0.20 for three-then-disturb) (E9).
- **Sparse, quiet breakdowns.** Breakdowns are brighter and busier, and only 1.3 dB down (A10).
- **Long, boomy 808 notes and deep glissandos.** Median note 0.6 beats, nothing past 1.4 bars, glides
  of 0.76 semitones (B5, B8).
- **One-bar loops, identical 1-4 bar phrases, and the two-step as default.** Lag-1 sits at the random
  baseline, and the two-step is 13% of runtime (E2, E5, K4).
- **Liquid-style long reverb and delay.** Nothing at or above a 1/4 (S4).

### Complicated

- **Subtraction is right, but narrower and shorter than the lore says.** Only the low end comes out,
  a median 19 dB, for about a bar (D1).
- **The pitch-envelope argument is resolved by both sides being half right.** +30 semitones deep,
  but a 12 ms time constant, so it's heard as the attack, not a slide (B4).
- **Fills.** On the 4-bar grid, yes, but they take one slot in four and prefer bar 3 of 4 and bar 2 of
  8, not the phrase end (E8).
- **"Half-time reggae bass".** The harmonic rhythm is roughly half-time, but the articulation is short
  and the intervals are steps, not roots and fifths (B7).
- **"Keep kick and snare steady".** The snare is steady; the kick is part of what moves (E4, K3).
- **The shuffle is occupancy, not swing.** Odd 16ths hit 0.34 of the time at 52.4% swing (E10).
- **Loudness.** Limited to 0 dBFS, yet transients survive (7.5 dB crest). Both the "dynamics" camp
  and the "compression" camp get part of it (S6).

### Where the lore is about something else

- **Track-writing, not DJ sets.** Templates (A1), second drops (A11), intro-length debates (A9) and
  build kits (D2) describe a record from bar 1. The set shows 40-192 bars per record, cuts over
  intros, and only the drops the DJ chose to keep. The forums have almost nothing on the shape of a
  set itself: 9 records in 21 minutes, handovers that are either 1-5 bar cuts or 8-32 bar blends and
  nothing in between, and bass removal as the preparation. That is the gap this measurement fills.
- **DnB, not jungle.** The sidechain threads, "proper drop" kits, liquid reverb, 4x4 debates and the
  400-500 Hz hat-loop layer are DnB or generic EDM advice. Where a thread was jungle-specific (KVR
  *Classic Jungle Bass Sound*, the Renoise and Elektronauts old-skool threads), it generally agrees
  with the measurement.
- **Old skool vs modern.** Most "jungle" lore describes 1993-95 records made on samplers. This is a
  2026 set of modern jungle. The two diverge where you'd expect: a cleaner sub, no pads, loud
  mastering. They agree where the forums call something the essence: breaks over programmed kits,
  sub over reese, short space.

---

## 3. Sources

### Fetch log: which workarounds worked

| route | result |
|---|---|
| Reddit: `old.reddit.com`, `www.reddit.com`, `.json` endpoints | **Blocked.** WebFetch refuses the domains. A WebSearch restricted to reddit.com returns an error that the domain is not accessible to Anthropic's crawler; Reddit opts out. Not bypassed. **Zero Reddit claims** (r/jungle, r/DnB, r/DnBproduction, r/WeAreTheMusicMakers, r/edmproduction). |
| Wayback Machine (`web.archive.org/web/2020*/...`), `archive.ph` | **Blocked.** WebFetch refuses both domains. |
| Google cache | Not attempted; Google retired public cache links in 2024. |
| Dogs On Acid, direct | **HTTP 403** on thread pages and on the XenForo RSS feed. |
| Dogs On Acid, search snippets | **Worked.** About 40 searches restricted to dogsonacid.com. Searching a thread's exact title tied the summary to that thread; search metadata supplied four dates. All DOA rows are S. |
| Gearspace | **HTTP 403** in both URL formats (`/threads/...` and `/board/...html`). Snippets only. |
| dnbforum.com, Discogs groups, ReasonTalk | **HTTP 403.** Snippets only. |
| KVR Audio, Renoise, Elektronauts, forum.ableton.com | **Fetched** without trouble. |
| Sound On Sound forum | **Fetched** only through the `...&embed=true` URL form; the plain URL returned navigation only. |
| Image-Line (FL Studio) forum | Partial: thread bodies are hidden when logged out. Nothing usable. |
| music.stackexchange, llllllll.co, Cycling '74, Bitwig, Sonic State, Rolldabeats | Searched; nothing usable on this topic. |
| Future Music forum, Polyverse, public Discord indexes | **Not reached.** The session's 200-search cap ran out. |

Coverage is uneven as a result. The Reddit view is entirely missing. DOA, the most jungle-specific
forum, is snippet-only, and the fetched material leans towards KVR, Renoise, Elektronauts and
Ableton users.

### Dogs On Acid (dogsonacid.com): all snippet-only (S)

| code | thread | year | URL |
|---|---|---|---|
| DOA 1 | DNB Structure | Oct 2014 | https://www.dogsonacid.com/threads/dnb-structure.765121/ |
| DOA 2 | Proper Tutorial for a DnB Drop!? | ~2024 | https://www.dogsonacid.com/threads/proper-tutorial-for-a-dnb-drop.829391/ |
| DOA 3 | how many bars ? | ~2008 | https://www.dogsonacid.com/threads/how-many-bars.597095/ |
| DOA 4 | MIXING JUNGLE AND IT'S DJ INTRO LENGTHS TODAY | ~2022 | https://www.dogsonacid.com/threads/mixing-jungle-and-its-dj-intro-lengths-today.819346/ |
| DOA 5 | Question to all the DnB DJs on here | ~2017 | https://www.dogsonacid.com/threads/question-to-all-the-dnb-djs-on-here.790257/ |
| DOA 6 | Making a solid 16-bar loop | ~2020 | https://www.dogsonacid.com/threads/making-a-solid-16-bar-loop.809809/ |
| DOA 7 | Bringing energy to beats and arrangements | ~2025 | https://www.dogsonacid.com/threads/bringing-energy-to-beats-and-arrangements.833288/ |
| DOA 8 | Stepper or Roller? | ~2018 | https://www.dogsonacid.com/threads/stepper-or-roller.793827/ |
| DOA 9 | Change in the definition of Roller... | ~2012 | https://www.dogsonacid.com/threads/change-in-the-definition-of-roller.727225/ |
| DOA 10 | some people don't know the difference between a 'stepper' and a 'roller'... | ~2017 | https://www.dogsonacid.com/threads/some-people-dont-know-the-difference-between-a-stepper-and-a-roller.788918/ |
| DOA 11 | Tonight, I would like to discuss Song Structure... | ~2012 | https://www.dogsonacid.com/threads/tonight-i-would-like-to-discuss-song-structure.728889/ |
| DOA 12 | 2nd drop? What's the point?? | ~2008 | https://www.dogsonacid.com/threads/2nd-drop-whats-the-point.556528/ |
| DOA 13 | What is a double drop? | ~2008 | https://www.dogsonacid.com/threads/what-is-a-double-drop.551684/ |
| DOA 14 | How does one go about mixing a double drop? | ~2009 | https://www.dogsonacid.com/threads/how-does-one-go-about-mixing-a-double-drop.614706/ |
| DOA 15 | Andy C interview on his mixing and double drops | ~2016 | https://www.dogsonacid.com/threads/andy-c-interview-on-his-mixing-and-double-drops.779339/ |
| DOA 16 | switching the basslines. | ~2006 | https://www.dogsonacid.com/threads/switching-the-basslines.341241/ |
| DOA 17 | Noob question: amen edits. | ~2008 | https://www.dogsonacid.com/threads/noob-question-amen-edits.574386/ |
| DOA 18 | Jungle/Amen break programming | ~2017 | https://www.dogsonacid.com/threads/jungle-amen-break-programming.787380/ |
| DOA 19 | What is the Theory behind Breakbeat/Jungle Fills | ~2023 | https://www.dogsonacid.com/threads/what-is-the-theory-behind-breakbeat-jungle-fills.823994/ |
| DOA 20 | Tips for 'dropping' Jungle | Oct 2024 | https://www.dogsonacid.com/threads/tips-for-dropping-jungle.827212/ |
| DOA 21 | Tips for good build up? | ~2017 | https://www.dogsonacid.com/threads/tips-for-good-build-up.788643/ |
| DOA 22 | Risers And Build Up Samples!!! | ~2008 | https://www.dogsonacid.com/threads/risers-and-build-up-samples.561129/ |
| DOA 23 | Riser sound FX? | ~2011 | https://www.dogsonacid.com/threads/riser-sound-fx.709172/ |
| DOA 24 | How do you make basic riser effects? | ~2014 | https://www.dogsonacid.com/threads/how-do-you-make-basic-riser-effects.761024/ |
| DOA 25 | Sidechain in DNB | 2008 | https://www.dogsonacid.com/threads/sidechain-in-dnb.565479/ |
| DOA 26 | Side chaining sub bass | Feb 2017 | https://www.dogsonacid.com/threads/side-chaining-sub-bass.785516/ |
| DOA 27 | Do you sidechain breaks to your kick and snare? | ~2023 | https://www.dogsonacid.com/threads/do-you-sidechain-breaks-to-your-kick-and-snare.825105/ |
| DOA 28 | How do you sidechain breakbeat "kicks"? | ~2007 | https://www.dogsonacid.com/threads/how-do-you-sidechain-breakbeat-kicks.450120/ |
| DOA 29 | Is there a rift between "jungle" and "drum & bass" right now? | ~2022 | https://www.dogsonacid.com/threads/is-there-a-rift-between-jungle-and-drum-bass-right-now.820171/ |
| DOA 30 | 808 Bass | ~2017 | https://www.dogsonacid.com/threads/808-bass.789900/ |
| DOA 31 | Jungle bass | ~2020 | https://www.dogsonacid.com/threads/jungle-bass.808133/ |
| DOA 32 | 808 bass questions | ~2019 | https://www.dogsonacid.com/threads/808-bass-questions.800795/ |
| DOA 33 | 92 - 95 oldschool jungle production help | ~2020 | https://www.dogsonacid.com/threads/92-95-oldschool-jungle-production-help.809029/ |
| DOA 34 | Writing 90s jungle basslines | ~2020 | https://www.dogsonacid.com/threads/writing-90s-jungle-basslines.809086/ |
| DOA 35 | any tips how to make jungle bassline ? | ~2015 | https://www.dogsonacid.com/threads/any-tips-how-to-make-jungle-bassline.770364/ |
| DOA 36 | Is the reese bass essential for drum and bass. | ~2014 | https://www.dogsonacid.com/threads/is-the-reese-bass-essential-for-drum-and-bass.764063/ |
| DOA 37 | Do you use the kicks and snares from a break? | ~2019 | https://www.dogsonacid.com/threads/do-you-use-the-kicks-and-snares-from-a-break.804805/ |
| DOA 38 | First Contact Amen Break Layering/Mixing? | ~2024 | https://www.dogsonacid.com/threads/first-contact-amen-break-layering-mixing.827751/ |
| DOA 39 | 4x4 Drum & Bass | ~2023 | https://www.dogsonacid.com/threads/4x4-drum-bass.822473/ |
| DOA 40 | Anyone else noticing a 4/4 beat trend in dnb? | ~2003 | https://www.dogsonacid.com/threads/anyone-else-noticing-a-4-4-beat-trend-in-dnb.130197/ |
| DOA 41 | 'modern' breakbeat over 4 to the floor kicks | ~2017 | https://www.dogsonacid.com/threads/modern-breakbeat-over-4-to-the-floor-kicks.790531/ |
| DOA 42 | Old skool style ragga jungle / jungle samples ?? | ~2017 | https://www.dogsonacid.com/threads/old-skool-style-ragga-jungle-jungle-samples.791337/ |
| DOA 43 | best sites for jungle-samples? | ~2018 | https://www.dogsonacid.com/threads/best-sites-for-jungle-samples.797949/ |
| DOA 44 | modern dnb/jungle production styles you DONT like | ~2024 | https://www.dogsonacid.com/threads/modern-dnb-jungle-production-styles-you-dont-like.826492/ |
| DOA 45 | Jungle Reverb | Sept 2009 | https://www.dogsonacid.com/threads/jungle-reverb.644729/ |
| DOA 46 | Maintaining Mono Compatibility with WIDE Stereo Sounds | ~2008 | https://www.dogsonacid.com/threads/maintaining-mono-compatibility-with-wide-stereo-sounds.593204/ |
| DOA 47 | What are the primary differences and similarities between the Drum And Bass, Jungle And Drumfunk genres of music? | ~2021 | https://www.dogsonacid.com/threads/what-are-the-primary-differences-and-similarities-between-the-drum-and-bass-jungle-and-drumfunk-genres-of-music.814318/ |
| DOA 48 | Why the original jungle sound will never die - Coco Bryce, Tim Reaper, Pete Cannon [Ukf] | ~2021 | https://www.dogsonacid.com/threads/why-the-original-jungle-sound-will-never-die-coco-bryce-tim-reaper-pete-cannon-ukf.811386/ |
| DOA 49 | Layering one shots with breaks | ~2023 | https://www.dogsonacid.com/threads/layering-one-shots-with-breaks.825347/ |
| DOA 50 | Mixing Bass - How to craft the perfect bottom end - Sound On Sound | ~2014 | https://www.dogsonacid.com/threads/mixing-bass-how-to-craft-the-perfect-bottom-end-sound-on-sound.767503/ |
| DOA 51 | Engineering-wise how did Pendulum and Noisia change the game? (cluster attribution) | ~2021 | https://www.dogsonacid.com/threads/engineering-wise-how-did-pendulum-and-noisia-change-the-game.814193/ |

### KVR Audio (kvraudio.com): all fetched (F)

| code | thread | year | URL |
|---|---|---|---|
| KVR 1 | What's the basic structure of a dance song? | 2005 | https://www.kvraudio.com/forum/viewtopic.php?t=111781 |
| KVR 2 | What is a "Drop" and a "Bar" in EDM song structure? | 2014 | https://www.kvraudio.com/forum/viewtopic.php?t=407134 |
| KVR 3 | Advanced Drum Programming Questions (for house music) | 2012 | https://www.kvraudio.com/forum/viewtopic.php?t=344525 |
| KVR 4 | EDM arrangements - the less elements the better? | 2013 | https://www.kvraudio.com/forum/viewtopic.php?t=382251 |
| KVR 5 | Drum and bass production advise | 2021 | https://www.kvraudio.com/forum/viewtopic.php?t=575123 |
| KVR 7 | Breakbeat drum programming? | 2010 | https://www.kvraudio.com/forum/viewtopic.php?t=289686 |
| KVR 8 | Traditional D&B drum & loop processing and composition | 2015 | https://www.kvraudio.com/forum/viewtopic.php?t=443896 |
| KVR 9 | jungle production - sixtuplets | 2022 | https://www.kvraudio.com/forum/viewtopic.php?p=8357737 |
| KVR 10 | Classic drum breaks for DnB converted to MIDI? | 2005 | https://www.kvraudio.com/forum/viewtopic.php?t=74288 |
| KVR 11 | Jungle beats | 2007 | https://www.kvraudio.com/forum/viewtopic.php?t=181304 |
| KVR 13 | how do you create those mad beats in oldskool hardcore? | 2008 | https://www.kvraudio.com/forum/viewtopic.php?t=203025 |
| KVR 14 | amen break (p2) | 2005 | https://www.kvraudio.com/forum/viewtopic.php?t=98231&start=15 |
| KVR 15 | Do you buss your Kick with Bass or with Drums? | 2015 | https://www.kvraudio.com/forum/viewtopic.php?t=449244 |
| KVR 16 | Perfect dnb/breakbeat kicks? | 2007 | https://www.kvraudio.com/forum/viewtopic.php?t=192931 |
| KVR 17 | DnB sound (design?) (p2) | 2017 | https://www.kvraudio.com/forum/viewtopic.php?start=15&t=481375 |
| KVR 18 | DnB Drum Question | 2008 | https://www.kvraudio.com/forum/viewtopic.php?t=229016 |
| KVR 19 | Classic Jungle Bass Sound (pages 1-2) | 2008-09 | https://www.kvraudio.com/forum/viewtopic.php?t=230797 |
| KVR 20 | Ragga Jungle Basslines.... (page 1 of 3) | 2007 | https://www.kvraudio.com/forum/viewtopic.php?t=178261 |
| KVR 21 | Drum and Bass/Jungle 'swell' bass sound (p2) | 2006 | https://www.kvraudio.com/forum/viewtopic.php?t=157023&start=15 |
| KVR 22 | How to mix a Reese bass? | 2017 | https://www.kvraudio.com/forum/viewtopic.php?t=486458 |
| KVR 23 | Sidechain Compression - Dance Music - Kick/Bass | 2007 | https://www.kvraudio.com/forum/viewtopic.php?t=172101 |
| KVR 24 | "Liquid" D&B Reverb | 2012 | https://www.kvraudio.com/forum/viewtopic.php?t=358521 |
| KVR 25 | Jungle Pads? | 2008 | https://www.kvraudio.com/forum/viewtopic.php?t=213420 |
| KVR 26 | noise-sweep transition thread (title not captured) | 2012 | https://www.kvraudio.com/forum/viewtopic.php?t=366133 |
| KVR 27 | Dub snare delay sound | 2017 | https://www.kvraudio.com/forum/viewtopic.php?t=491630 |

(KVR 6, *Jungle/Break-beat pattern writing?*, 2016, https://www.kvraudio.com/forum/viewtopic.php?t=459056,
and KVR 12, *The Prodigy Breaks?*, 2019, https://www.kvraudio.com/forum/viewtopic.php?t=531330&start=15,
were read but only yielded technique: pitch rather than stretch, zone-per-hit re-ordering, and
retrigger start points. Neither is structural, so neither appears in the tables.)

### Gearspace (gearspace.com): all snippet-only (S), years estimated from thread IDs

| code | thread | year | URL |
|---|---|---|---|
| GS 1 | Arranging in electronic music | ~2023 | https://gearspace.com/board/electronic-music-instruments-and-electronic-music-production/1414602-arranging-electronic-music.html |
| GS 2 | How do you structure your beats (candidate; attribution not confirmed) | ? | https://gearspace.com/threads/how-do-you-structure-your-beats.941321/ |
| GS 3 | Basic structure of EDM songs...??? (attribution not confirmed) | ~2015 | https://gearspace.com/board/electronic-music-instruments-and-electronic-music-production/1006729-basic-structure-edm-songs.html |
| GS 4 | This old jungle/breakbeat production method? | ~2014 | https://gearspace.com/board/electronic-music-instruments-and-electronic-music-production/947516-old-jungle-breakbeat-production-method.html |
| GS 5 | Layering breakbeats & 808/909 kicks - any EQ/filtering tips? | ~2016 | https://gearspace.com/board/rap-hip-hop-engineering-and-production/1103205-layering-breakbeats-amp-808-909-kicks-any-eq-filtering-tips.html |
| GS 6 | 90's Drum and Bass (attribution not confirmed) | ~2013 | https://gearspace.com/board/electronic-music-instruments-and-electronic-music-production/832783-90s-drum-bass.html |
| GS 7 | How do you make breakbeats (candidate) | ? | https://gearspace.com/threads/how-do-you-make-breakbeats.791950/ |
| GS 8 | Jungle Bass Production | ~2023-24 | https://gearspace.com/board/electronic-music-instruments-and-electronic-music-production/1424591-jungle-bass-production.html |
| GS 9 | 90s Jungle bass help! | ~2016 | https://gearspace.com/board/electronic-music-instruments-and-electronic-music-production/1109445-90s-jungle-bass-help.html |
| GS 10 | Question for OG jungle and UKG producers | ~2021 | https://gearspace.com/board/electronic-music-instruments-and-electronic-music-production/1369709-question-og-jungle-ukg-producers.html |
| GS 11 | Reggae, Dub, Jungle, DnB, Dubstep, history. | ~2010 | https://gearspace.com/threads/reggae-dub-jungle-dnb-dubstep-history.477662/ |

### Renoise forum (forum.renoise.com): fetched (F)

| code | thread | year | URL |
|---|---|---|---|
| REN 1 | Old-skool Jungle Production | 2014 | https://forum.renoise.com/t/old-skool-jungle-production/42025 |
| REN 2 | Learning about sample-loops/ahmens removed my interest in Break-Beat music | 2023 | https://forum.renoise.com/t/learning-about-sample-loops-ahmens-removed-my-interest-in-break-beat-music/69911 |
| REN 3 | How To Make A Jungle/dnb Bass Sound (pages 1-2) | 2009-16 | https://forum.renoise.com/t/how-to-make-a-jungle-dnb-bass-sound/26901 |
| REN 4 | Sidechaining, it's not even that great | 2015 | https://forum.renoise.com/t/sidechaining-its-not-even-that-great/44165 |
| REN 5 | D&b Basses | 2007 | https://forum.renoise.com/t/d-b-basses/20282 |
| REN 6 | Common bass synth in Jungle | 2016 | https://forum.renoise.com/t/common-bass-synth-in-jungle/45815 |
| REN 7 | Drum And Bass Schema Ideas/Suggestions | 2011 | https://forum.renoise.com/t/drum-and-bass-schema-ideas-suggestions/33029 |
| REN 8 | A few questions for Jungle/Breakcore/Drill n' Bass producers | 2022 | https://forum.renoise.com/t/a-few-questions-for-jungle-breakcore-drill-n-bass-producers/67110 |
| REN 9 | Ragga Samples | 2011 | https://forum.renoise.com/t/ragga-samples/30923 |
| REN 10 | How do you program old school jungle? (read for the earlier brief, `tracks/2026-09-15_jungle_research.md` [17]) | - | https://forum.renoise.com/t/how-do-you-program-old-school-jungle/27145 |

(REN 2's point, about 70% of time going into break programming and loop reuse being dull unless
transformed, is consistent with E1 but not measurable, so it has no row. REN 6 is history, not
structure: the reese traces to Kevin Saunderson on a Casio CZ.)

### Elektronauts (elektronauts.com): fetched (F)

| code | thread | year | URL |
|---|---|---|---|
| ELK 1 | Elektronauts dnb/jungle tunes/tips (pages 6, 13, 14) | 2022-24 | https://www.elektronauts.com/t/elektronauts-dnb-jungle-tunes-tips/176785?page=13 |
| ELK 2 | Classic Jungle on the OT | 2020 | https://www.elektronauts.com/t/classic-jungle-on-the-ot/125662 |
| ELK 3 | Drum programming/ Jungle/ Aphex Twin (pages 1, 4) | 2016-18 | https://www.elektronauts.com/t/drum-programming-jungle-aphex-twin/33540 |
| ELK 4 | Can the OT do Oldschool Jungle? (pages 1-2) | 2015 | https://www.elektronauts.com/t/can-the-ot-do-oldschool-jungle/14183 |
| ELK 5 | Live Snare-Roll-Build-ups: Techniques | 2024 | https://www.elektronauts.com/t/live-snare-roll-build-ups-techniques/208097 |

### Ableton forum (forum.ableton.com, archived): fetched (F)

| code | thread | year | URL |
|---|---|---|---|
| ABL 1 | dance music structure | 2008 | https://forum.ableton.com/viewtopic.php?t=87631 |
| ABL 2 | My lame-ass attempt at D N' B | 2006 | https://forum.ableton.com/viewtopic.php?t=54872 |
| ABL 4 | getting that drop | 2010 | https://forum.ableton.com/viewtopic.php?f=1&t=153275 |
| ABL 5 | Jungle Drop Bass Sound | 2005 | https://forum.ableton.com/viewtopic.php?f=4&t=24730 |
| ABL 6 | Properly Sidechaining/Sub bass-Kick relationship: Dubstep/Dnb | 2016 | https://forum.ableton.com/viewtopic.php?t=220701 |
| ABL 7 | Deep Bass And How To | 2009 | https://forum.ableton.com/viewtopic.php?t=119440 |
| ABL 8 | DnB Tips.. | 2008 | https://forum.ableton.com/viewtopic.php?t=101663 |

(ABL 3, *Why Drum n' Bass? Or Give me a break!*, 2009, https://forum.ableton.com/viewtopic.php?t=104423:
learn a narrow genre's rules first, and DnB is harder to DJ than 4x4. Nothing testable.)

### Other forums

| code | forum and thread | year | URL | seen |
|---|---|---|---|---|
| SOS 1 | Sound On Sound: Any techniques for getting the drum and bass in drum and bass right | 2009-10 | https://forum.soundonsound.com/phpbb/viewtopic.php?p=153085&embed=true | F |
| DNBF 1 | dnbforum.com: D&B song structure. | ? | https://dnbforum.com/threads/d-b-song-structure.72726/ | S (403) |
| DNBF 2 | dnbforum.com: Drum & Bass Structure & Arrangement (attribution uncertain) | ? | https://dnbforum.com/threads/drum-bass-structure-arrangement.73788/ | S (403) |
| DISC 1 | Discogs group: D&B vs Jungle | ? | https://www.discogs.com/group/thread/551895 | S (403) |

### Not a forum

| code | page | seen |
|---|---|---|
| WEB 1 | Wayne & Wax, *Digital Music - Lesson Three: Form* (a course page on dancehall and hip-hop form; used only as the nearest source for "three bars and a fill") https://wayneandwax.com/org/lessons/musiclesson3.html | F |
