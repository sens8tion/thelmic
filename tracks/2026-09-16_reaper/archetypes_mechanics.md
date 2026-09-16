# Jungle archetypes vs the Reaper measurements: the mechanics

What the gear, manuals, circuit papers and producer write-ups say about ten measurements from the
Reaper set (`bass.md`, `rhythm.md`, `mix-space.md`, `hooks.md`, `drops.md`, `structure.md`). This
page covers mechanics only: circuits, samplers, sequencers and effects. It is paraphrased, with no
quotes. Source IDs like **[M4]** point to part 3, which says whether each source was **fetched**,
**snippet-only** or **pointer** (Wikipedia, read only to find other sources).

**How far to trust the sourcing.**
- **Search cap.** The session hit its web-search limit after about 17 searches of mine, so most
  sources were fetched from known URLs or found through links on pages already fetched.
- **Blocked sites.** Reverb.com, Gearspace, Dogs On Acid, Discogs, the Guardian, archive.org,
  ModWiggler and Google Groups all refused to load. Anything from those is snippet-only.
- **Primary sources.** The strongest evidence here is four manuals and circuit papers: the Akai
  S950, S1000 (v2.0, 1989) and S2000 manuals, the Werner/Abel/Smith 808 circuit paper (2014) and
  Deruty's 808 paper (2024).
- **Few period voices.** Almost nothing is a 1990s producer describing his own low end. Most
  "classic jungle" claims are retrospective, from 2008-2026.

---

## 1. The sub's "bell": +30 st falling with τ 12 ms, on 0-94% of notes by record

**Measured.**
- **Onset pitch.** Wide-band pitch reads +17.1 st at 0-10 ms, +10.4 at 10-20 ms, +7.0 at 20-30 ms
  and +2.3 at 30-45 ms.
- **Fitted envelope.** The best fit is +30 st with τ = 12 ms, plus a +1 st tail with τ ≈ 200 ms.
- **Spread.** 76% of clean notes start at least 3 st sharp. By record the share runs from 94% (S17)
  and 88% (S14) down to 0-12% (S22, S25, S09).
- **Tone.** It is a clean sub: h2 is 16.6 dB under the fundamental. The median clean note is
  47.4 Hz.

**What the sources say.**
- **The archetype is well attested, but only in retrospect.** Several sources say a sampled 808
  kick, lengthened and pitched, became the jungle sub:
  - Wikipedia's drum-and-bass article, as a pointer
  - Reason Studios 2025 **[M12]**: 808 sine tones sampled into an S950
  - KVR 2008 **[M14]**: a resampled 808 was the typical source
  - Renoise forum 2015 **[M18]**: long-decay 808s pitched for the sub
  - Attack 2021 **[M10]**: bounce one note and trigger it from a sampler for an old-school jungle
    sound
  - Amped Studio 2026 **[M13]**

  A second family is the Akai sine or "test tone" sub. The S1000 manual confirms that a SINE sample
  is the default in a new program **[M5]**. The "test tone" name itself is snippet-only
  (Gearspace, Dogs On Acid, Discogs). Renoise 2009 **[M17]** recommends a plain sine sub.
- **A stock TR-808 kick does not match the measured sweep.** The circuit papers describe two
  separate pitch effects:
  - **An attack jump.** The bridged-T filter's frequency rises by more than an octave for about
    6 ms, which is less than one cycle at the raised pitch **[M1]**. Barata's analysis puts it at
    about 49.4 Hz rising to about 130 Hz, roughly +16.7 st, for about 6 ms **[M3]**.
  - **A slow "sigh".** Leakage in the circuit pulls the pitch down slightly as the note decays
    **[M1][M3]**. Deruty measured 37 long 808 samples and found the median sweep over 0.2 s windows
    is about a semitone **[M2]**.

  So a stock 808 starts about as sharp as the reference in its first 10 ms (+16.7 vs +17.1 st). It
  should then be back to the sigh level by the 10-20 ms bin, but the reference is still +10 st
  there and +7 st at 20-30 ms. The reference sweep lasts roughly five times longer. Transposing the
  sample can't fix that: stretching 6 ms to 30 ms means playing it about 28 st down, which would
  put the fundamental near 10 Hz. The +1 st, τ ≈ 200 ms tail is the same size and shape as the
  808's sigh.
- **The samplers had a pitch envelope built in.**
  - **S950 (WARP).** The manual describes WARP as a pitch sweep on the attack. A positive "attack
    offset" makes the pitch slide down onto the note, with separate time and velocity controls
    **[M4]**.
  - **S1000.** A second ADSR can be routed to pitch, up to ±50 **[M5]**.

  So a sine sub with WARP or an envelope on pitch, or an "808-style" synth patch (a sine plus a
  pitch envelope, as in Attack 2021 **[M10][M11]**), can have a longer sweep than the 808 circuit.
  Neither manual gives the sweep depth in semitones, so +30 st cannot be checked against the
  hardware.
- **Why it changes by record.** The sources describe several sub recipes in use at once: 808
  resamples, sine or test-tone subs, an FM bass (the DX100 "Solid Bass" preset, KVR 2008 **[M14]**)
  and distorted 808s run through a sampler and desk (Dillinja, snippet-only). A mix of records
  using different recipes gives a ping on some records and none on others. S25 has no ping and the
  most odd-harmonic grit, which fits a distorted sine better than a pinging 808.
- **Sine in jungle, reese in drum and bass.** This is too simple. Reason Studios 2025 **[M12]**
  dates the reese to Kevin Saunderson's 1988 patch and calls it a jungle staple too. Wikipedia's
  techstep and neurofunk pages (pointers) tie the distorted reese to 1995-98 techstep and
  neurofunk.

| claim | verdict | measured |
|---|---|---|
| The jungle sub is often a sampled, pitched long-decay 808, or an Akai sine | **CONFIRMED** (retrospective sources only; no 1990s source) | clean sub, h2 −16.6 dB; ping on 76% of clean notes |
| The bell is a stock TR-808 kick's pitch jump | **CONTRADICTED** by its length | +10.4 st at 10-20 ms, where an 808 is already settled (~6 ms jump) |
| The +1 st slow tail is 808-like | **NUANCED** (same size as the 808 sigh; a sampler envelope could also make it) | +1 st, τ ≈ 200 ms |
| A sampler or synth pitch envelope on a sine can make the long sweep | **NUANCED** (S950 WARP and S1000 envelope-to-pitch exist; depth in semitones undocumented) | +30 st, τ 12 ms |
| Different sub recipes in different records | **NUANCED** (plausible; records are unattributed) | 0-94% ping by record |
| Sine is jungle, reese is drum and bass | **NUANCED** (the reese was in jungle by 1994) | the set has no reese |

## 2. No sidechain: −0.5 dB duck; kick and sub split by register instead

**Measured.**
- **Duck.** The sub moves −0.5 / −0.3 / −0.4 dB at 0-30 / 30-80 / 80-200 ms after the kick.
  Measured inside a note it rises +2.3 dB at the kick, and 0 of 14 sections duck more than 4 dB.
- **Register.** The kick puts 42.5% of its energy at 60-250 Hz; the bass puts 73.8% below 60 Hz.

**What the sources say.**
- **Nothing documents that 1990s jungle avoided sidechaining.** The mechanics make it unlikely,
  though. The period rigs were an Akai with mono outputs (8 on the S950 **[M4]**) into a desk and an
  Atari running Cubase. Nookie's 1993 setup, for example, was an S950, a Studiomaster 16-channel
  desk, an Atari with Cubase and a DAT machine **[M20]**. Ducking would have needed an outboard
  compressor with a key input on the bass channel. And in 58% of bars (§6) the kick is inside the
  break, so there is no separate kick to key from. That last step is my inference, not a source.
- **When sidechaining entered drum and bass is undocumented.**
  - The technique dates from 1930s film sound; pumping reached house and electro in the late 1990s
    (The Linx 2026 **[M39]**).
  - Daft Punk's "One More Time" (2000) and Eric Prydz's "Call On Me" (2004) are the usual pop
    examples (snippet-only).
  - The only drum-and-bass trace found is a 2010 forum memory of an undated Future Music interview:
    Rob Swire of Pendulum ducked keyboard lines with a Waves C1, not the bass (KVR **[M16]**,
    hearsay).
  - Modern tutorials duck drum layers rather than the sub. Attack 2012 keys the ride from the kick
    and snare **[M24]**. Attack 2023 ducks the break about 8 dB from the kick **[M26]**. Magnetic
    Mag 2026 prefers band-limited ducking **[M38]**.
- **Splitting by register is documented.** Attack 2012 high-passes the kick at about 85 Hz to make
  room for the bassline **[M24]**. Magnetic Mag 2026 treats sub and mid-bass as separate jobs
  **[M38]**.
- **The modern producer doesn't rely on period limits.** Tim Reaper has used FL Studio since 2009
  with no outboard gear (Beatportal 2021 **[M32]**), so sidechaining was always available to him.
  Any lack of it in his own records is a choice. The set mixes records by several producers,
  though, so this can't be pinned to him.

| claim | verdict | measured |
|---|---|---|
| Kick and sub are separated by register | **CONFIRMED** (documented technique) | kick 42.5% at 60-250 Hz; bass 73.8% below 60 Hz |
| 1990s jungle did not sidechain the bass | **NOT MEASURABLE** from sources (no source either way; mechanics make it unlikely) | −0.5 dB; 0/14 sections below −4 dB |
| Modern drum and bass ducks the bass under the kick | **CONTRADICTED** by this set; tutorials mostly duck drum layers instead | +2.3 dB in-note at the kick |
| When sidechaining entered drum and bass | **unexplained** (no dated source) | — |

## 3. Portamento: 41% of transitions glide, median 96 ms, 0.76 st, 59% falling

**Measured.**
- **Glides.** 2.5 glide runs a bar; median 96 ms and 0.76 st; 59% fall.
- **Many are the onset ping.** bass.md §9.4 found 48% of glide runs start within 100 ms of a note
  start, and 71% of those fall. The tracker's 160 ms window smeared the onset drop into a glide.
- **The rest.** The remaining runs fall 47% of the time.
- **Size.** Glided moves are small (median 1.05 st); jumped moves are larger (median 2.05 st).

**What the sources say.**
- **Half of it is §1 again.** The between-note glides that are left are balanced up and down. That
  is what real portamento looks like: the direction follows the melody. The 808's sigh would add a
  small downward drift after each onset **[M1]**.
- **The mechanisms existed across the eras.**
  - S950: pitch wheel, default range 7 st **[M4]**
  - S1000 v2.0 (1989): bend wheel up to ±12 st, and envelope to pitch; I found no portamento in its
    text **[M5]**. A 2010 KVR user remembers S1000 portamento **[M15]**, which may be a later OS
    (unverified).
  - S2000: portamento in rate or time mode, plus mono legato **[M6]**
  - FL Studio: a Mono and Porta mode with a Slide knob; in FL the glide also carries cutoff and pan
    **[M7]**. This is Reaper's DAW **[M32]**.
  - Attack 2021's 808-bass tutorial turns glide on for one pair of notes **[M11]**.
- **"Long sliding notes" is the wrong picture.** The half-tempo reggae bassline with long slides
  (Orphiq 2026 **[M37]**; KVR 2008 **[M14]**) doesn't match what was measured. The glides are short
  scoops, the median note is 0.60 beats, and nothing is held past 1.4 bars.

| claim | verdict | measured |
|---|---|---|
| Much of the glide is the 808-style onset drop | **CONFIRMED** (internal evidence, plus the 808 sigh in [M1]) | 48% of runs at onsets, 71% of those falling |
| The rest is sampler or DAW portamento or pitch-bend | **NUANCED** (all mechanisms documented; which one was used can't be recovered) | rest 47% falling; median 1.05 st |
| Jungle bass uses long sliding notes | **CONTRADICTED** | 96 ms, 0.76 st; note median 0.60 beats |

## 4. The 16th carrier: a break high-passed at 80-320 Hz on the 16ths, with the full break stacked under it at drops

**Measured.**
- **Coverage.** A carrier is present in 74.5% of bars (68% after correcting for false alarms).
- **Type by bars.** Full-range break 68%, high-passed break 26%, short percussion 6%.
- **Filter corner.** 83-319 Hz; high-passed sections sit at 197-308 Hz.
- **Decay.** Hits decay before the next 16th (15-30 ms to half level).
- **At drops.** 0 of 15 drops replace the carrier; 125-500 Hz body grows a median +1.2 dB under it.
  The filter does not open at the drop (median corner 167 → 176 Hz).

**What the sources say.**
- **Layering high-passed breaks over a kick or skeleton is standard and documented.**
  - Attack 2023: the break is high-passed at 214 Hz, cut at 303 Hz and low-passed at 4.84 kHz over
    a separate kick. A shaker loop high-passed at 1.91 kHz carries the very top **[M26]**. The
    break's corner sits in the same place as the measured high-passed carriers (S3 208 Hz, S5
    263 Hz).
  - Attack 2012: several breaks layered with "bracketing" EQ, and a high-passed ride kept only for
    air **[M25]**. Another 2012 piece layers a programmed kick, snare and ride with a raw re-sliced
    break **[M24]**.
  - Renoise forum 2009: stack several breaks on the same sample offsets for a rolling texture
    **[M17]**. A 2015 post offsets layered breaks by 1-1.5 beats **[M18]**.
  - Future Music 2022 describes the 90s jungle groove itself as several breaks layered **[M23]**.
- **The short hits fit chopping.** Paradox leaves small gaps between hat and snare slices, keeps
  breaks mono and centred, and builds "shuffles" from hat-snare sequences **[M19]**.
- **Not documented:** keeping the high-passed layer running at the drop while full-range material
  arrives under it, and leaving its filter where it was.

| claim | verdict | measured |
|---|---|---|
| A high-passed break layered over the main drums is a documented technique | **CONFIRMED** | corners 197-308 Hz in high-passed sections; 26% of bars |
| A layer carries the 16ths most of the time | **CONFIRMED** as practice (no source gives a share) | 74.5% of bars (68% corrected) |
| At the drop the full break stacks under the carrier rather than replacing it | **NUANCED** (fits layering practice; not described anywhere) | 0/15 replaced; +1.2 dB body |
| The drop opens the break's filter | **CONTRADICTED** (the sweep is not the delivery) | corner 167 → 176 Hz; opens 4 times, closes 4 times in 17 drops |

## 5. A-B-C-D bars: lag-1 is the least alike, the 4-bar group returns

**Measured.**
- **Similarity by lag.** Lag-1 similarity is 0.355, equal to two random bars from the same section
  (0.356). Lag 4 is 0.486, lag 8 is 0.465 and lag 2 is 0.436.
- **Fills.** 4-bar periodic (autocorrelation +0.19 at lag 4).
- **Chopping.** Even near-identical bars differ by 4.6 ms of microtiming, so nothing is a looped
  bar of audio.

**What the sources say.**
- **Trackers work in 4-bar blocks of 16ths.**
  - A MOD pattern has 64 rows (Wikipedia pointer). The Renoise forum 2009 **[M17]** advises
    beginners to use 64-line patterns at 4 lines a beat, which is exactly 4 bars of 16ths, and to
    build a track from 4-8 such patterns.
  - Jungle producers who used OctaMED on the Amiga include Paradox **[M19]**, and Wikipedia also
    lists Aphrodite, Bizzy B, DJ Zinc and Omni Trio (pointer).
  - The same 2009 thread describes re-dealing a break inside a pattern: sample-offset commands
    (9xx) fire slices of one synced loop, even interpolated across a block **[M17]**. That rebuilds
    every bar from the same source, which is what the chop tests found.
- **Atari sequencers and samplers were the other route.** The Atari running Cubase with an Akai
  was the standard UK rig (Future Music 2020 **[M22]**). Remarc used an Atari ST and an S950 and
  chopped more heavily than his peers **[M21]**; Nookie's 1993 remix used an S950 with Cubase
  **[M20]**. No fetched source describes Cubase-on-Atari parts as 4-bar blocks.
- **The source breaks are 4-bar phrases, but they don't give A-B-C-D.** The Amen is four bars,
  about 7 s at about 136 BPM (Wikipedia pointer). Its first two bars are the same funk groove;
  bars 3-4 move the snare, swap the ride for an open hat and change the kick (Hein 2023 **[M27]**).
  Played straight, that is A-A-B-C, which would push lag-1 similarity *up*.
- **Tutorials make 4-bar sequences but don't state the rule.** Attack 2023 builds 4 bars from two
  segments, one reversed **[M26]**. Computer Music 2011 re-triggers slices by dragging MIDI notes
  **[M28]**.
- **Photek built his breaks from single hits** with varied attack velocities (2021 retrospective
  **[M42]**).

| claim | verdict | measured |
|---|---|---|
| The 4-bar return comes from 4-bar sequencing units (tracker patterns, 4-bar breaks, 4-bar edits) | **NUANCED** (documented for trackers and tutorials, not shown to be universal) | lag 4 0.486, lag 8 0.465 |
| The bar is re-dealt from slices rather than looped | **CONFIRMED** (sample-offset and slice practice) | 4.6 ms microtiming difference even in near-identical bars |
| Consecutive bars are deliberately made the least alike | **unexplained** (no source states it; the Amen played straight is the opposite) | lag 1 0.355 = random 0.356 |

## 6. Kick styles: break kick 58%, sparse 26%, two-step 13%, no four-on-the-floor; the bass barely moves under a two-step

**Measured.**
- **Kick style by runtime.** Break kick 58.0%, sparse or syncopated 25.7%, two-step 12.6%, no kick
  3.8%, four-on-the-floor 0%.
- **Bass movement by kick style.** The bass changes 0.25 times a bar under a two-step (3 sections),
  against 1.02 under a break kick (14 sections).
- **Carrier.** Under a two-step the 16th layer is absent or short percussion in 82% of bars.

**What the sources say.**
- **The two-step belongs to drum and bass; the chopped break belongs to jungle.** Future Music 2022
  **[M23]** lists sliced and layered breaks as the '90s jungle groove. It files the two-step (second
  kick on the 8th before the second snare) under drum and bass.
- **When and why it arrived.** Wikipedia (pointers only):
  - Techstep, around 1995-97, favoured quantised drum-machine kits and hardstep kicks and snares.
  - Neurofunk moved to more regular two-step rhythms away from jungle's dense polyrhythms. The page
    cites Simon Reynolds' essay "2 Steps Back" (The Wire, December 1997), which I couldn't fetch.

  The sources give only style reasons: techno and science-fiction influence. None gives a technical
  one.
- **Why the bass might sit still over a two-step.**
  - **Rollers.** The roller is described as repetitive drums changing every 16-32 bars under a deep,
    hypnotic bassline (In-Reach 2020 **[M34]**).
  - **Neurofunk.** It moves the bass's *timbre* over a steady low component, not its pitch
    (Wikipedia pointer).
  - **808 gain.** For 808 bass, Scott Storch keeps the pitch largely static so the level doesn't
    jump from note to note, because low fundamentals lose perceived gain when transposed down
    (Deruty 2024 **[M2]**). That matches bass.md §4, where "busy and deep are alternatives": the
    sections that change 0.25-0.42 times a bar put 73-92% of the low end below 60 Hz.

  No source links the static bass to the two-step kick itself.

| claim | verdict | measured |
|---|---|---|
| Jungle kicks mostly come from the break; four-on-the-floor is absent | **CONFIRMED** | 58% break kick, 0% four-on-the-floor |
| The two-step arrived with mid-90s techstep and neurofunk | **NUANCED** (Wikipedia pointers only; the Reynolds 1997 essay not fetched) | 12.6% of runtime, 2 sub-sections |
| The bass barely moves under a two-step | **NUANCED** (fits the roller and neurofunk descriptions and Deruty's gain logic; n = 3 sections) | 0.25 vs 1.02 changes/bar |
| A programmed kick comes with a thin 16th layer | **unexplained** | 82% absent or short percussion |

## 7. Subtraction drops: 82% set up by pulling the low end with the break running; zero risers

**Measured.**
- **Devices.** Subtraction 82%, with the low end down a median 19.2 dB. Rolls 27%, filter sweeps
  23%, gaps 27%, tonal calls 18%, risers 0%.
- **Approach.** The level falls into the drop (−1.3 dB).
- **Seams.** 4 of 8 record changes are prepared by 3-7 bars of bass removal (structure.md).

**What the sources say.**
- **Bass removal is a documented device, but one of several.** EDMProd 2025 **[M36]** lists
  dropping the drums, swapping the break, filtering, removing the bass and a reverse crash or
  upsweep, all as eight-bar turnarounds. KAN Samples 2026 **[M35]** gives the modern drum-and-bass
  build as white-noise risers, snare rolls, opening filters, extra percussion and silence. Bass
  removal isn't on its list.
- **Risers aren't dated.** The "bass drop" is traced to Miami bass and the 808 (Wikipedia pointer).
  The EDM build-up of snare acceleration and swelling synths is described without a date. No source
  says when risers entered drum and bass, or that jungle avoided them.
- **Some of it may be the DJ.** A DJ mixer's bass EQ, or a bass kill on some models, removes the
  low end of one channel (Wikipedia pointer). This is a DJ set and its seams show bass removal, so
  some subtraction drops may be performed on the mixer rather than written into the records. The
  measurement can't separate the two. Tim Reaper learned on a Traktor controller (snippet-only).

| claim | verdict | measured |
|---|---|---|
| Dropping the sub is a classic jungle drop device | **NUANCED** (documented as one option; its dominance is not) | 82% of drops, −19.2 dB |
| Risers are a later drum and bass or EDM convention | **NOT MEASURABLE** from sources (modern tutorials use them; no date found) | 0 of 22 |
| The subtraction is written into the records | **NOT MEASURABLE** (DJ EQ can make the same result) | seams prepared by 3-7 bars of bass removal |

## 8. Delays and space: 120 / 181 / 45 ms, nothing at 1/4; mono below 150 Hz; width moves with events

**Measured.**
- **Delays.** 1/8 triplet ≈ 120 ms (16.3% of drop repeats), 1/8 ≈ 181 ms (6.1%), 1/32 ≈ 45 ms
  (6.6%). 1/4 and longer are at or below the 3.1% chance level.
- **Low end.** Side is −32.9 dB under mid below 150 Hz.
- **Width.** The side image lives at 400 Hz-2 kHz, and its bar-locked autocorrelation is only
  0.13-0.21.

**What the sources say.**
- **Mono samplers and effect sends explain the mono bass and the event-driven width.**
  - S950: 8 individual mono outputs plus a pseudo-stereo L/R pair **[M4]**.
  - S1000: a mono effect send with a stereo return, switchable per sample, so a dry hat can sit next
    to a "live" tom. It also has an LFO auto-pan **[M5]**. The measurements show no cyclic panning,
    so the auto-pan was not the source of width.
  - Paradox keeps breaks mono and centred and uses a Roland reverb rack, TC Electronic delays and
    Alesis ambience units. He also samples the room between hits and reverses slices to make
    tails, rather than adding reverb afterwards **[M19]**.
  - Nookie's Cloud 9 remix (1993) was completely dry **[M20]**.
  - Dub practice: throw effects on selected hits, a big reverb on the odd snare rather than every
    one, unsynced delays with filtered feedback (MusicRadar 2007 **[M30]**; Orphiq 2026 **[M37]**).

  So width arrives on the hits that are sent to effects. That matches the "event-driven, not an
  LFO" result.
- **Vinyl may also require mono bass.** Cutting stereo vinyl may force low frequencies to mono.
  That is my hypothesis; I found no source.
- **Why these delay times: no source.** Nothing names 1/8 triplet or 1/8 as a jungle convention,
  and period units could all go well past 362 ms. Two further notes:
  - **Detector caveat.** The echo detector needs a gap as long as the lag, and dense breaks rarely
    leave 362 ms of space (only 23 hits qualified at 1/4 in drops, mix-space.md §4c). "Nothing at
    1/4" is therefore partly a detection limit.
  - **Timestretch hypothesis for 45 ms.** Akai cyclic timestretch repeats audio at a fixed cycle
    length set in samples **[M5]**, and its artefacts are metallic and stuttering **[M29]**. The
    45 ms "slapback" could be timestretch grain repetition rather than a delay unit. No source
    supports this.

| claim | verdict | measured |
|---|---|---|
| Low end mono, width on the mids | **CONFIRMED** as consistent with mono sampler outputs and centred breaks | side −32.9 dB below 150 Hz |
| Stereo movement comes from per-hit sends and throws, not auto-pan | **CONFIRMED** (mechanism documented; the S1000 auto-pan exists but is not used here) | bar-locked autocorrelation 0.13-0.21 |
| Period effects conventions dictate short delays | **unexplained** | 120 / 181 / 45 ms |
| No delays at 1/4 or longer | **NOT MEASURABLE**, partly (detection needs long gaps) | 1.2% at 1/4 against 3.1% chance |

## 9. Hook register: 233-392 Hz fundamentals, a 10 dB valley at 233 Hz, 39% of bars, median 1.2 beats

**Measured.**
- **Register.** Hook fundamentals have an IQR of 233-392 Hz (median 277 Hz). The spectral valley
  sits at 233 Hz, −9.9 dB deep. The bass tops out at 174 Hz.
- **Frequency.** Hooks appear in 39% of bars; median event 1.2 beats; 81% are under 2 beats.

**What the sources say.**
- **Sampler bandwidth shapes the top, not the register.**
  - The S950 samples at up to 48 kHz and 12 bits, with bandwidth variable from 3 to 19.2 kHz. Less
    bandwidth buys memory at the cost of a muffled sound, and the manual has a per-instrument
    bandwidth chart **[M4]**.
  - The S1000 offers 44.1 kHz with 20 kHz bandwidth or 22.05 kHz with 10 kHz, and its low-pass
    filter is 18 dB per octave without resonance **[M5]**.

  These limits remove brightness. They do not move fundamentals to 233-392 Hz.
- **Cutting around 250-300 Hz is documented, but not for this reason.** Attack 2023 cuts the break
  at 303 Hz **[M26]**. The earlier brief's mixing source cuts pads around 250 Hz. Neither says the
  cut is there to separate hooks from bass.
- **Nothing documents where the hooks sit.** No source sets a register for ragga vocals, stabs or
  pads. Orphiq 2026 places ragga vocals on the slow half-tempo grid, but says nothing about pitch
  **[M37]**.

| claim | verdict | measured |
|---|---|---|
| Sampler bandwidth limits shaped the hook register | **CONTRADICTED** as an explanation (limits affect the top octave, not fundamentals) | fundamentals 233-392 Hz |
| A low-mid EQ notch separates hooks from bass | **NUANCED** (cuts at 250-300 Hz are documented, not for this purpose) | valley 233 Hz, −9.9 dB |
| Short hooks (stabs and chants) in low-mids are convention | **unexplained** | 39% of bars, median 1.2 beats |

## 10. Key: D#/E♭ minor

**Measured.**
- **Key fit.** 84.6% of bass sounding time lies in D# minor / F# major.
- **Pitch classes.** F# carries 33.5% and D# 17.0%. 16 of 25 sections fit the key at least 80%.
- **Pitch.** The median clean note is 47.4 Hz, a little above F#1 (46.2 Hz).

**What the sources say.**
- **The 808's own pitch.** The 808 kick's natural fundamental is about 49.4-49.5 Hz, which is G1
  **[M1][M2][M3]**. Werner's model gives 49.5 Hz, against 56 Hz on Roland's own tuning chart
  **[M1]**.
- **Storch's rule.** Scott Storch moves the song's key to suit the 808 rather than retuning the 808.
  Transposing a lone 49.5 Hz fundamental down a fourth costs about 11.8 dB of perceived level on
  near-field monitors, speaker and ear together. With five partials the loss is only about 4.5 dB
  **[M2]**. This is a hip-hop practice, not a jungle one.
- **A related claim.** EDMProd 2025 **[M36]** calls E to G the sub sweet spot.
- **How that fits the set.**
  - The sub's centre (47.4 Hz) is 0.7 st below the 808's natural pitch, and the most-played pitch
    class, F#, is the note one semitone below G.
  - D#1 (38.9 Hz) is 4 st lower. Measured over the set, busy sections carry less energy below
    60 Hz.

  That is consistent with keeping the sub near the 808's register, but it is not evidence of it.
- **Why the whole set holds one key.** DJs harmonic-mix, pairing tracks in related keys (Mixed In
  Key **[M40]**). That explains a key-coherent set with whole-record excursions. It does not explain
  why E♭ minor.
- **Jungle keys.** No source gives a jungle key convention. The earlier brief's "F minor" was never
  sourced either.

| claim | verdict | measured |
|---|---|---|
| Subs are tuned near the 808 sample's natural pitch | **NUANCED** (consistent; the Storch practice is hip-hop, not jungle) | median 47.4 Hz vs 808 at 49.4 Hz; F# 33.5% |
| The set is key-coherent through DJ harmonic mixing | **NUANCED** (DJ practice documented; Reaper's use of it not sourced) | 84.6% in D#m/F#M; 16/25 sections ≥ 80% |
| Jungle has a conventional key (D#m or Fm) | **unexplained** | D#/E♭ minor |

---

### Claims from the earlier brief, re-checked (mechanics only)

| brief claim (tag) | now | source |
|---|---|---|
| S950 "bandwidth = rate / 2.5" [snippet] | **CONFIRMED**: 48 kHz maximum rate with 19.2 kHz bandwidth, variable 3-19 kHz | [M4] fetched manual |
| S950 grit came from driving the input hot [snippet] | still snippet-only; not in the manual | — |
| Retrigger and sample-start offsets for rolls [snippet] | **CONFIRMED** as tracker practice (9xx offsets, interpolated) | [M17] |
| A second break layered only for character and top end [snippet] | **CONFIRMED** (bracketing EQ; break high-passed at 214 Hz over a kick) | [M25][M26] |
| Reggae roots, fifths and glides [snippet] | **NUANCED**: half-tempo reggae bass is stated, but the set moves by steps more than fifths (28.5% 1-2 st, 7.4% fifths) and glides are short | [M14][M37]; bass.md §3 |
| Short early-reflection reverb [snippet] | **NUANCED**: tails often come from room sound or reversed slices, and some records were dry | [M19][M20] |
| Sine sub or long 808 | **CONFIRMED**, with the 808 sweep caveat in §1 | [M12][M14][M17][M18] |
| Sidechain 1-5 ms attack, 80-150 ms release | **CONTRADICTED** by the set (−0.5 dB) | bass.md §6 |
| F-minor progressions [unsourced] | still unsourced; the set is D#m | — |

## 2. Measurements no archetype explains

- **The length of the bell.** A +30 st, τ 12 ms sweep that is still +10 st at 10-20 ms. It runs
  about five times longer than a stock TR-808's roughly 6 ms attack jump. Sampler pitch envelopes
  could make it, but no source documents their depth.
- **Consecutive bars as unlike as random ones** (lag-1 0.355 vs 0.356) inside a 4-bar group that
  returns. The 4-bar unit has mechanical explanations; deliberately maximising difference between
  neighbouring bars has none, and the Amen played straight does the opposite.
- **The delay times.** 1/8 triplet as the dominant delay, 1/8 second, a 45 ms slap, and nothing
  found at 1/4 or longer. No period unit or convention explains the choice, and the missing long
  delays are partly a detection limit.
- **Hook fundamentals at 233-392 Hz** with a valley at 233 Hz. Sampler bandwidth limits can't
  explain fundamentals, and nothing documents the register.
- **E♭ minor.** No key convention found. DJ harmonic mixing explains set-level coherence only.
- **A still bass under a programmed two-step** (0.25 vs 1.02 changes a bar, only 3 sections), and a
  thin or absent 16th layer under a two-step (82%). The roller and neurofunk descriptions are
  suggestive, nothing more.
- **Stacking at the drop.** The carrier keeps its low-cut, and full-range body arrives beneath it
  (+1.2 dB at 125-500 Hz). Layering is documented; this drop-specific stacking is not.
- **The sub rising +2.3 dB at the kick.** No source addresses it. The likely cause is the kick's own
  sub energy, which is my inference.
- **Zero risers.** Nothing dates the riser in drum and bass, or says jungle avoided it. DJ EQ could
  also account for part of the 82% subtraction.

## 3. Sources

Each entry gives author, date, title and URL. **Fetched** means the page (or PDF text) was read in
this session; **snippet-only** means only a search-result summary was seen; **pointer** means
Wikipedia, used only to find other sources.

**Primary: manuals, circuits, papers**
- **[M1]** Kurt James Werner, Jonathan Abel, Julius O. Smith, 2014, "A Physically-Informed,
  Circuit-Bendable, Digital Model of the Roland TR-808 Bass Drum Circuit", DAFx-14. **Fetched**
  (PDF). https://dafx14.fau.de/papers/dafx14_kurt_james_werner_a_physically_informed,_ci.pdf
- **[M2]** Emmanuel Deruty, 2024 (ISMIR 2024; arXiv v2 2026), "Harmonic and Transposition
  Constraints Arising from the Use of the Roland TR-808 Bass Drum". **Fetched** (PDF).
  https://arxiv.org/abs/2502.07524
- **[M3]** Peter Barata, Baratatronix, undated, "Roland TR 808 Bass Drum Synthesis". **Fetched**.
  https://www.baratatronix.com/blog/808-bd-synthesis
- **[M4]** Akai, S950 Owner's Manual, undated (late 1980s). **Fetched** (PDF).
  https://manuals.fdiskc.com/flat/Akai%20S-950%20Owners%20Manual.pdf
- **[M5]** Akai, S1000 Operator's Manual, software v2.0 (page footers dated 89/11). **Fetched**
  (PDF). https://www.firstpr.com.au/rwi/smem/akai-manuals/S1000-V2.0-Manual.pdf
- **[M6]** Akai, S2000 Operator's Manual v1.30, undated. **Fetched** (PDF).
  https://www.polynominal.com/akai-s2000/akai-s2000-manual.pdf
- **[M7]** Image-Line, FL Studio manual, "Miscellaneous Channel Settings", current. **Fetched**.
  https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/chansettings_misc.htm
- Gordon Reid, Sound On Sound, Jan 2002, "Synthesizing Drums: The Bass Drum": acoustic kick pitch
  drifts a couple of semitones. **Fetched**.
  https://www.soundonsound.com/techniques/synthesizing-drums-bass-drum
- Gordon Reid, Sound On Sound, Feb 2002, "Practical Bass Drum Synthesis": the 808 uses a bridged-T
  circuit and goes slightly flat at long decays; the 909 uses a pitch envelope. **Fetched**.
  https://www.soundonsound.com/techniques/practical-bass-drum-synthesis

**Producers and period practice**
- **[M19]** Joseph Joyce, Ableton, 8 Feb 2022, "Paradox: Breakbeat Mastery". **Fetched**.
  https://www.ableton.com/en/blog/paradox-breakbeat-mastery/
- **[M20]** Ben Murphy, DJ Mag, 5 Apr 2022, Nookie "Cloud 9" remix feature. **Fetched**.
  https://djmag.com/features/how-nookies-gonna-be-alright-cloud-9-remix-foresaw-hardcores-jungle-evolution
- **[M21]** Ben Cardew, Line Noise, 27 May 2026, Remarc. **Fetched**.
  https://linenoise.substack.com/p/a-remarc-of-obsession-saluting-the
- **[M42]** T.Q. Kelley, Ghost Deep, 25 Jun 2021, "Photek: modus operandi". **Fetched**.
  https://ghostdeep.substack.com/p/photek-modus-operandi
- **[M32]** Joe Rihn, Beatportal, 15 Feb 2021, Tim Reaper cover story (FL Studio since 2009, no
  outboard). **Fetched**.
  https://www.beatportal.com/articles/12703-cover-story-tim-reaper-believes-jungle-can-do-almost-anything-it-wants-to
- **[M33]** Paddy Edrich, UKF, 2020, "In Conversation With Tim Reaper": traces back to original
  samples rather than rebuilding hardware rigs. **Fetched**.
  https://ukf.com/words/in-conversation-with-tim-reaper/27803
- **[M31]** Chal Ravens, Native Instruments blog, undated, "Sketches: Sully": a kick with a looped
  wave cycle in its tail used as the bass. **Fetched**. https://blog.native-instruments.com/sketches-sully/
- Chris Korff, Sound On Sound, Aug 2020, "Retro Jungle Production With Pete Cannon": a video page
  with no technical text. **Fetched**.
  https://www.soundonsound.com/techniques/retro-jungle-production-pete-cannon

**Technique write-ups**
- **[M10]** Adam Douglas, Attack Magazine, 6 Jan 2021, "808-Style Booms". **Fetched**.
  https://www.attackmagazine.com/technique/synth-secrets/808-style-booms/
- **[M11]** Adam Douglas, Attack Magazine, 1 Sep 2021, "Creating 808-Style Basslines For Jungle,
  Trap And Footwork". **Fetched**.
  https://www.attackmagazine.com/technique/tutorials/creating-808-style-basslines-for-jungle-trap-and-footwork/
- **[M24]** Attack Magazine, 26 Jun 2012, "Beat Dissected: Raw Drum & Bass". **Fetched**.
  https://www.attackmagazine.com/technique/beat-dissected/raw-drum-bass/
- **[M25]** Attack Magazine, 28 Jun 2012, "Beat Dissected: Incessant Drum & Bass". **Fetched**.
  https://www.attackmagazine.com/technique/beat-dissected/incessant-drum-bass-beat/
- **[M26]** Dan Brashaw, Attack Magazine, 24 Jul 2023, "Slicing Breakbeats Like Nia Archives".
  **Fetched**. https://www.attackmagazine.com/technique/beat-dissected/slicing-breakbeats-like-nia-archives/
- **[M12]** Saul Mountford, Reason Studios, 7 Sep 2025, "Jungle 101: Let's Talk Bass". **Fetched**.
  https://www.reasonstudios.com/news/post/jungle-101-lets-talk-bass
- **[M13]** Antony Tornver, Amped Studio, 2 Jun 2026, "808 Bass Guide". **Fetched**.
  https://ampedstudio.com/blog/secrets-of-808-bass/
- **[M22]** Future Music / MusicRadar, 16 Jun 2020, "Everything you need to know about: Jungle".
  **Fetched**. https://www.musicradar.com/news/everything-you-need-to-know-about-jungle
- **[M23]** Future Music / MusicRadar, 17 Feb 2022, "How to program 6 different jungle and drum 'n'
  bass grooves". **Fetched**. https://www.musicradar.com/how-to/program-6-different-jungle-6-dnb-grooves
- **[M28]** Computer Music / MusicRadar, 20 Jun 2011, "How to make old skool jungle-style breaks".
  **Fetched**. https://www.musicradar.com/tuition/tech/how-to-make-old-skool-jungle-style-breaks-464788
- **[M29]** Future Music / MusicRadar, 2 Dec 2014, "Authentic timestretched jungle breaks with
  Akaizer". **Fetched**.
  https://www.musicradar.com/tuition/tech/how-to-create-authentic-timestretched-jungle-breaks-with-akaizer-611255
- **[M30]** MusicRadar, 28 Nov 2007, "25 dub tips". **Fetched**.
  https://www.musicradar.com/tuition/tech/25-dub-tips-34138
- **[M27]** Ethan Hein, 8 May 2023, "Building the Amen break". **Fetched**.
  https://ethanhein.substack.com/p/building-the-amen-break
- **[M34]** Ellie Jones, In-Reach, 3 Feb 2020, "What is a roller?". **Fetched**.
  https://in-reach.co.uk/what-is-a-roller/
- **[M35]** KAN Samples, 31 May 2026, "Drum and Bass Track Structure & Arrangement". **Fetched**.
  https://kansamples.com/blogs/learn/dnb-track-arrangement
- **[M36]** Simon Haven, EDMProd, 23 May 2025, "How to Make Jungle Music". **Fetched**.
  https://www.edmprod.com/how-to-make-jungle-music/
- **[M37]** JC Sanchez, Orphiq, 19 Aug 2026, "What is jungle music". **Fetched**.
  https://orphiq.com/resources/what-is-jungle-music
- **[M38]** Will Vance, Magnetic Magazine, 10 Jun 2026, jungle production tips. **Fetched**.
  https://magneticmag.com/2026/06/music-production-tips-for-making-jungle/
- **[M39]** Truman Greene, The Linx, 8 Sep 2026, "What is sidechaining anyway?". **Fetched**.
  https://thelinx.substack.com/p/what-is-sidechaining-anyway
- **[M40]** Mixed In Key, updated Sep 2024, "Harmonic Mixing Guide". **Fetched**.
  https://mixedinkey.com/harmonic-mixing-guide/

**Forums (fetched; practitioner testimony, weak)**
- **[M14]** KVR, Oct 2008, "Classic Jungle Bass Sound". https://www.kvraudio.com/forum/viewtopic.php?t=230797
- **[M15]** KVR, Aug 2010, "Portamento on sample". https://www.kvraudio.com/forum/viewtopic.php?t=294887
- **[M16]** KVR, Sep 2010, "Pendulum lead sound?": a recollection of an undated Future Music
  interview (hearsay). https://www.kvraudio.com/forum/viewtopic.php?t=297081
- **[M17]** Renoise forum, Dec 2009-Jan 2010, "How do you program old school jungle".
  https://forum.renoise.com/t/how-do-you-program-old-school-jungle/27145
- **[M18]** Renoise forum, Oct 2015, "Getting that old skool jungle sound".
  https://forum.renoise.com/t/getting-that-old-skool-jungle-sound/44455

**Pointers (Wikipedia, fetched, used only to find leads)**
- Drum and bass: https://en.wikipedia.org/wiki/Drum_and_bass
- Techstep: https://en.wikipedia.org/wiki/Techstep
- Neurofunk (cites Simon Reynolds, "2 Steps Back", The Wire no. 166, Dec 1997, not fetched):
  https://en.wikipedia.org/wiki/Neurofunk
- Amen break: https://en.wikipedia.org/wiki/Amen_break
- OctaMED: https://en.wikipedia.org/wiki/OctaMED
- MOD file format: https://en.wikipedia.org/wiki/MOD_(file_format)
- Roland TR-808: https://en.wikipedia.org/wiki/Roland_TR-808
- Drop (music): https://en.wikipedia.org/wiki/Drop_(music)
- DJ mixer: https://en.wikipedia.org/wiki/DJ_mixer
- Darkcore: https://en.wikipedia.org/wiki/Darkside_jungle
- Hardstep: https://en.wikipedia.org/wiki/Hardstep

**Snippet-only (pages blocked or not fetched)**
- Reverb.com, "The Samplers and Breakbeats Behind '90s Jungle/Drum & Bass" (403):
  https://reverb.com/news/the-samplers-behind-90s-jungle-and-drum-and-bass
- Discogs group, "Analogue synths / sounds / samples in Jungle and early Dnb" (403): Akai S950
  test tone as a sub. https://www.discogs.com/group/thread/698172
- Gearspace, "Question for OG jungle and UKG producers" (403): 808 samples or Akai sines with a
  pitch envelope.
  https://gearspace.com/board/electronic-music-instruments-and-electronic-music-production/1369709-question-og-jungle-ukg-producers.html
- Gearspace, "Akai S950 Sub Bass. Is it worth it just for the bass?" (403):
  https://gearspace.com/board/so-much-gear-so-little-time/1196824-akai-s950-sub-bass-worth-just-teh-bass.html
- Dogs On Acid, "808 Bass" (403): an 808 or 909 kick with a long decay.
  https://www.dogsonacid.com/threads/808-bass.789900/
- Dogs On Acid, "Akai test tone bass" (403): https://www.dogsonacid.com/threads/akai-test-tone-bass.809102/
- Dogs On Acid, "how do ya make 808 bass like dillinja?": an 808 through an E-mu sampler with desk
  distortion. https://www.dogsonacid.com/threads/how-do-ya-make-808-bass-like-dillinja.368617/
- rec.music.makers.synth, "Jungle Bass synth" (429): https://groups.google.com/d/topic/rec.music.makers.synth/ILjbPg1t4jg
- eMastered / Antares sidechain guides: the 1930s origin, and Daft Punk and Prydz as pumping
  exemplars. https://emastered.com/blog/sidechain-compression ·
  https://www.antarestech.com/blog/what-is-sidechain-compression
- Tim Reaper interview (UKF/Tempo), per search summary: learned to DJ on a Traktor controller.
  https://t3mpo.com/tim-reaper-jungle-can-do-almost-anything-it-wants-to-interview/
