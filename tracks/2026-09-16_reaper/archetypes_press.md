# Jungle archetypes in the press, books and lectures, checked against the Reaper set

What journalism, histories, lectures and academic writing say jungle is *built like*, set claim by
claim against the measurements in this folder ([README.md](README.md), [alignment.md](alignment.md)
and the seven reports). Gathered 2026-09-16. Forum lore is in
[archetypes_forums.md](archetypes_forums.md); production tutorials are in
`../2026-09-15_jungle_research.md`. Neither is repeated here.

Everything is paraphrased. Quoted words are rare, each under 15 words, and never more than one
quote per source.

**How to read it**

- **Seen**: **F** = the page was fetched and read. **F\*** = read in full from a copy of the text
  held somewhere else: an RBMA lecture transcript read from the `ewenme/rbma-lectures` mirror, or
  Fintoni's rewind piece read from a repost. **2** = secondary: we only know the claim because a
  fetched source quotes or summarises it. **S** = search snippet only. 2 and S rows are weaker.
- **Type**: *essay* (magazine criticism), *feature* (journalism or history), *interview*,
  *lecture* (RBMA talk by a practitioner), *academic* (peer-reviewed or scholarly book), *review*.
- **Era** is the music the claim describes, not the date it was written. That matters: most of the
  structural writing describes 1992-97 records, and the measurement is a **2026 revival DJ set**.
- **Verdict**: CONFIRMED / CONTRADICTED / NUANCED / NOT MEASURABLE, with the number that decides it.
- **Scope warning**: one 21-minute section of one DJ set (Tim Reaper, 166 BPM, 9 records). A DJ cuts
  most intros, outros and breakdowns away, so claims about *whole records* are often only half
  visible. The verdict says what this set shows, not whether the writer was wrong about 1994.

Source links in the tables go straight to the page. Section 3 lists them with fetch status.

## 1. Claims

### 1.1 Phrasing and form

| # | claim (paraphrased) | source | type | seen | era | verdict and the number |
|---|---|---|---|---|---|---|
| P1 | D&B is essentially an 8-bar loop that repeats, and the producer's job is to keep it interesting. Beats and bassline come first. | Marcus Intalex, RBMA lecture, 2003 [[L-MI]](https://www.redbullmusicacademy.com/lectures/marcus-intalex-the-liquidator/). Quote: "very much like an 8-bar loop thing" | lecture | F\* | 2003 D&B | **NUANCED.** The 8-bar phrase is the strongest period in the set (lag excess +0.181), riff sub-sections run a median 8 bars, and literal similarity at 8 bars is 0.50. But it is never a *loop*: neighbouring bars are the least alike (lag-1 0.355), and even pattern-identical bars differ by 4.6 ms of microtiming. The grid is strictly 4-bar (100% of sections) and only loosely 8 (84%). |
| P2 | Modern D&B tracks give a 16-bar intro and then they are in. In a one-hour set a DJ picks records he knows arrive after 32 bars, and in long sets lets them run past 48. | Zinc, RBMA lecture, 2005 [[L-ZN]](https://www.redbullmusicacademy.com/lectures/zinc-hardware-bingo/) | lecture | F\* | 2005 D&B | **CONFIRMED.** Drops are a median **33.5 bars** apart. Section lengths peak at 32 bars (7 exact) and 16 (4 exact). The intros that survive the mix are 16-34 bars of bassless break (0:00 for 34 bars, 19:27 for 16). |
| P3 | The stock D&B structure is a 64-bar drum intro, a breakdown, a main body of about 128 bars, a second breakdown, a mix-out point and an outro. Colman finds it predictable and goes looking for surprise. | Tony Colman (London Elektricity), RBMA lecture, 2003 [[L-TC]](https://www.redbullmusicacademy.com/lectures/tony-colman-gravytrain/). Quote: "That's boring." | lecture | F\* | 2003 D&B | **NUANCED, mostly NOT MEASURABLE.** The DJ removes most of this: 5 of 8 seams are 1-5 bar cuts. What is visible is records played for 40-192 bars (median 72) and breakdowns taking only **2.8%** of runtime. No 64-bar drum intro appears apart from the 34-bar opener. |
| P4 | Goldie drew each track as a storyline for his engineer (Rob Playford): where the breaks sit, where things drop out, where the pads fall, where the bassline switches. | Goldie, RBMA lecture, 2008 [[L-GO]](https://www.redbullmusicacademy.com/lectures/goldie-ramblas-in-the-jungle/) | lecture | F\* | 1994-95 | **NOT MEASURABLE** (it describes his process). Nearest measurement: section changes are planned events where several layers change at once. 3-4 layers turn over on the same bar in 16% of events against 2% by chance, and 7 of the 12 big turnovers fall *inside* records, not at the DJ's seams. |
| P5 | Ambient jungle tracks were built like architecture: build-up and breakdown, climax and afterglow. | Simon Reynolds, *The Wire* #127, 1994 [[W94]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_2_ambient-jungle_1994_) | essay | F | 1994 | **CONTRADICTED for this set.** Builds are 4.8% of runtime and breakdowns 2.8%. There is no layered build-in (bar 2 is within 0.5 dB of bar 1), and breakdowns are only 1.3 dB quieter. *Era gap*: album-minded ambient jungle, against a set that edits breakdowns out. |
| P6 | Hardstep held one plateau of pressure, with no rises and no dips. | Reynolds, *The Wire* #148, 1996 [[W96]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_4_hardstep_jump-up_techstep_1996_). Quote: "no crescendos or lulls" | essay | F | 1996 | **CONFIRMED.** The set is "full" **86%** of its runtime. None of the 22 drops has a riser. Per-minute RMS varies by only 5.9 dB, and a drop adds just +2.6 dB RMS. |
| P7 | These are tracks, not songs, built on repetition. A record is usable to a DJ only if it has the right drops. | Reynolds, *Energy Flash* blog, 2009 [[EF09]](http://energyflashbysimonreynolds.blogspot.com/2009/02/hardcore-continuum-or-theory-and-its.html) | essay | F | 1990s-2000s | **CONFIRMED.** 22 drops in 21 minutes, with a structural event every ~15 bars. Nothing returns the way a chorus would: no record comes back, and within a record the main loop comes back 40-84% verbatim. |
| P8 | By 1993 jungle sat around 160 BPM. By the 2000s D&B was at 170 and up. Fabio thought 175 was too fast, and that 160 would lose the "clowny" feel. | Christodoulou, *Dancecult*, 2020 [[CH20]](https://dj.dancecult.net/index.php/dancecult/article/view/1153); Joe Rihn, Beatportal, 2021 [[BP21]](https://www.beatportal.com/articles/4445-beatports-definitive-history-of-drum-bass); Fabio, RBMA, 2006 [[L-FA]](https://www.redbullmusicacademy.com/lectures/fabio-the-root-to-the-shoot/) | academic, feature, lecture | F, F, F\* | 1993 / 2000s | **NUANCED.** The set runs at **166.0 BPM** on one master clock (four estimates agree to 0.03 BPM). That is between the 1993 and 2000s figures, close to Fabio's suggestion. |
| P9 | "Serenity" (J Majik) opens with about a minute of held chords and nature sounds before any break. | Christodoulou 2020 [[CH20]](https://dj.dancecult.net/index.php/dancecult/article/view/1153) | academic | F | 1990s ambient | **NOT MEASURABLE** per record, because an intro plays under the previous record. The intros you can hear in the set are breaks only, never pads: 5 of 287 melodic events are sustained tones. |

### 1.2 Structure for the DJ and the dance: mixing, doubles, rewinds, the MC

| # | claim (paraphrased) | source | type | seen | era | verdict and the number |
|---|---|---|---|---|---|---|
| D1 | D&B DJs took live blending of two tunes further than anyone before them, using the crossfader. A mix should be able to flip a set's mood. | DJ Storm, RBMA talk, 2018 [[L-ST]](https://www.redbullmusicacademy.com/lectures/dj-storm-lecture/) | lecture | F\* | 1990s-2018 | **NUANCED.** Only 3 of 8 seams are real blends (8-32 bars, 12-46 s), and one is a 32-bar double-play that alternates bar by bar. The other 5 are hard cuts of 1-5 bars. Nothing falls in between. |
| D2 | Pirate-radio hardcore DJs strung short chunks of tracks into a relentless patchwork that was far from seamless, with MC chants on top. | Reynolds, *The Wire* #105, 1992 [[W92]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_1_hardcore-rave_1992_) | essay | F | 1992 | **CONFIRMED** for the mix's shape: 9 records in 21 minutes, a median **72 bars (104 s)** each, and cuts outnumber blends 5 to 3. |
| D3 | Double drop: line up two records so their basslines drop at the same moment, by counting bars against the 8- and 16-bar structure. Andy C uses three decks. | Andy C, interviewed by Becca Frankland, Skiddle, 2016 [[SK16]](https://www.skiddle.com/news/all/Andy-C-interview-Double-drop/28832/); Andy C credited with coining it (Dancing Astronaut, 2014, snippet) | interview | F (S) | mid-90s on | **NUANCED.** Phrasing is strictly 4-bar and only loosely 8 (84%). The set's one doubled-percussion passage (2 bars at 1.9× the onset norm, bass at 0.3%) sits right before the biggest bass entry of its section, at 10:04. Two basslines dropping at once was not tested. |
| D4 | The rewind came into jungle from Jamaican sound systems at raves like Telepathy and AWOL. It is called by the crowd or the MC in the moment, not planned. | Laurent Fintoni, *Cuepoint*, 2015 [[LF15]](https://www.dub-stuy.com/wheel-it-up-history-of-the-rewind/) | feature | F\* | 1991-2000s | **NOT MEASURABLE.** No rewind test was run. The single clock (one 30 ms phase step in 21 minutes) and the fact that no record returns both suggest there were none. Recorded sets rarely carry rewinds anyway. |
| D5 | The rewind, and MCs working over live DJ mixes, are what separate this lineage from house and techno. | Reynolds, *Energy Flash* blog, 2009 [[EF09]](http://energyflashbysimonreynolds.blogspot.com/2009/02/hardcore-continuum-or-theory-and-its.html); Reynolds, interviewed by Sam Backer, Afropop Worldwide, 2016 [[AP16]](https://www.afropop.org/articles/first-draft-simon-reynolds-interview) | essay, interview | F | 1990s-2000s | **NOT MEASURABLE** (same as D4; no MC analysis either). |
| D6 | Once producers became DJs, tunes turned formulaic, written for instant impact and for as many rewinds as possible. | dBridge, RBMA lecture, 2005 [[L-DB]](https://www.redbullmusicacademy.com/lectures/dbridge-many-rivers-to-cross/) | lecture | F\* | early-2000s D&B | **NOT MEASURABLE.** Related: newness is spent at the seam (the first sections of a record are 75-100% new), and after that the loop returns. |
| D7 | In a set that mixes records from 1992 to 1998, expect a rewind and use it to reset the pitch. | DJ Storm, 2018 [[L-ST]](https://www.redbullmusicacademy.com/lectures/dj-storm-lecture/) | lecture | F\* | old-school sets | **NOT MEASURABLE.** The measured set does the opposite: one tempo held for all 21 minutes. |
| D8 | The MC interprets the music for the crowd. Jungle raves needed one, though Fabio kept MCs out of his own club night. | Fabio, RBMA, 2006 [[L-FA]](https://www.redbullmusicacademy.com/lectures/fabio-the-root-to-the-shoot/) | lecture | F\* | 1991-2006 | **NOT MEASURABLE.** No MC analysis was run. 38 of 287 melodic events are vocal-like, but they were not split into MC and sampled vocals. |
| D9 | A good MC knows when to go quiet, and stops talking when a record's own vocal comes in. | Zinc, 2005 [[L-ZN]](https://www.redbullmusicacademy.com/lectures/zinc-hardware-bingo/); dBridge, 2005 [[L-DB]](https://www.redbullmusicacademy.com/lectures/dbridge-many-rivers-to-cross/) | lecture | F\* | 2000s | **NOT MEASURABLE.** |
| D10 | Storm dislikes sets that loop sections and never reach the drop, because they lose the atmospheric space. | DJ Storm, 2018 [[L-ST]](https://www.redbullmusicacademy.com/lectures/dj-storm-lecture/) | lecture | F\* | 2018 | **NUANCED.** This set reaches a drop every 33.5 bars, and its reduced passages are short (median 2.1 bars). The space is not long quiet sections. It is empty odd 16ths (occupancy 0.34) and short, steady tails (T20 299 ms). |

### 1.3 Breaks

| # | claim (paraphrased) | source | type | seen | era | verdict and the number |
|---|---|---|---|---|---|---|
| K1 | Jungle's rhythms are breaks that have been sped up, edited and processed until they are jagged and still groovy. This "breakbeat science" is the music's core. | Reynolds, *Energy Flash* blog, 2009 [[EF09]](http://energyflashbysimonreynolds.blogspot.com/2009/02/hardcore-continuum-or-theory-and-its.html); *The Wire* #136, 1995 [[W95]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_3_the-state-of-drum_n_bass_1995_) | essay | F | 1992-95 | **CONFIRMED.** The break is chopped and re-chopped every bar. Slice cut-offs line up with the 16th grid 20× more than chance, 4.8 per bar. Nothing is looped: even pattern-identical neighbouring bars differ by 4.6 ms of microtiming (a real loop would be 0-1 ms). |
| K2 | Where hip-hop loops a break at moderate tempo, D&B producers break it into its smallest parts and rebuild asymmetric patterns at speed. | Dale Chapman, *Echo*, 2003, via Christodoulou 2020 [[CH20]](https://dj.dancecult.net/index.php/dancecult/article/view/1153) | academic | 2 | 1990s-2000s | **CONFIRMED** (same numbers as K1). |
| K3 | In jungle the drum pattern is the hook, as memorable as any synth line. | Reynolds, *The Wire* #136, 1995 [[W95]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_3_the-state-of-drum_n_bass_1995_). Quote: "its drum-patterns are as catchy as its synth-motifs" | essay | F | 1995 | **CONFIRMED.** Drums run through the whole set, even the quietest breakdown (11.1 onsets per bar), and a 16th carrier is present in ~70-75% of bars. Melodic events fill only **12%** of runtime. |
| K4 | Break rhythms play down the strong beats and put the stress on weak positions. | Mark J. Butler, *Unlocking the Groove*, 2006, via Christodoulou 2020 [[CH20]](https://dj.dancecult.net/index.php/dancecult/article/view/1153) | academic | 2 | EDM breakbeat styles | **NUANCED, leaning CONTRADICTED.** The strong positions are heavily used: beat slots 0.83-0.87, kick on slot 0 at 0.91, snares on 4 and 12 at 0.94 and 0.89. Odd 16ths are only 0.34. The syncopation is the second kick on slot 10 (0.66) and the ghost notes, laid over a firmly marked backbeat. |
| K5 | A break repeats a difference inside itself: call and answer sound together, and the break is fractured throughout. | Christodoulou 2020, after Anne Danielsen, 2006 [[CH20]](https://dj.dancecult.net/index.php/dancecult/article/view/1153) | academic | F | 1990s-2019 | **CONFIRMED.** Bars run A-B-C-D: lag-1 similarity is 0.355, no higher than random bars, while lag-4 is 0.486. The low band carries the 4-bar return (lag-4 excess +0.137, the highest of the three bands). The "three repeats then a disturbance" pattern is not supported (p = 0.20). |
| K6 | Reinforced's early records used quick changes instead of long grooves, following Goldie's "hyper-speed" thinking. | Hanna Bächer, RBMA Daily, 2016 (4hero interview) [[RD16]](https://daily.redbullmusicacademy.com/2016/04/reinforced-interview/) | interview | F | 1991-93 | **NUANCED.** The surface changes every bar (lag-1 0.355), but the slow layers hold steady: the kick pattern for ~28 bars, the carrier for ~32, the bass riff for ~8. Fast on top, slow underneath. |
| K7 | Jungle is sequenced music and not ashamed of it (Omni Trio). | Martin James, *State of Bass*, 1997, via Christodoulou 2020 [[CH20]](https://dj.dancecult.net/index.php/dancecult/article/view/1153) | book | 2 | 1995-97 | **CONFIRMED.** Timing is straight: 52.4% swing after level correction, with 8th-note placements spread only 7.5 ms. Placement is quantised; the human feel is in the content. |
| K8 | D&B is very on the bar, "one-twos", with no room for quantise tricks. | dBridge, 2005 [[L-DB]](https://www.redbullmusicacademy.com/lectures/dbridge-many-rivers-to-cross/) | lecture | F\* | 2005 D&B | **CONFIRMED.** The revival set is just as straight (see K7). |
| K9 | Rufige Cru's "Terminator" (1992) was the first record to timestretch a break. 4hero found the technique in the Akai S950 manual. It changes tempo without changing pitch. | Martin James, *The Quietus*, 2020 [[Q20]](https://thequietus.com/articles/28122-state-of-bass-jungle-drum-bass-book-martin-james-playlist); RBMA Daily, 2016 [[RD16]](https://daily.redbullmusicacademy.com/2016/04/reinforced-interview/); Reynolds, 1994 [[W94]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_2_ambient-jungle_1994_) | feature, interview, essay | F | 1992-94 | **NOT MEASURABLE.** We did not analyse stretch artefacts, and the shared feature cache is 8 kHz mono. |
| K10 | The Amen is *the* break. Amen, Apache and a few others are the regulars, and the Amen now comes in endless variants. | Digital, RBMA, 2004 [[L-DG]](https://www.redbullmusicacademy.com/lectures/digital-roots-rocker/); dBridge, 2005; DJ Storm, 2018; Rihn, Beatportal, 2021 [[BP21]](https://www.beatportal.com/articles/4445-beatports-definitive-history-of-drum-bass) | lecture, feature | F\*, F | 1992-now | **NOT MEASURABLE.** Break identity was deliberately not analysed, and nothing was sampled. |
| K11 | A tightly coiled snare roll was hardstep's constant motif, and drum rolls were big in late-90s D&B. | Reynolds, 1996 [[W96]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_4_hardstep_jump-up_techstep_1996_); Marcus Intalex, 2003 [[L-MI]](https://www.redbullmusicacademy.com/lectures/marcus-intalex-the-liquidator/) | essay, lecture | F, F\* | 1996-2003 | **CONTRADICTED for this set.** Rolls come before only **27%** of drops. Fills are 6.5% of bars and only 1.23× busier than a normal bar. A fill here is a slightly busier bar, not a roll. *Era gap*: hardstep and late-90s D&B. |
| K12 | Revival jungle is intricate, unpredictable break editing, and turns its back on D&B's mechanical boom-clack two-step. | Ben Murphy, *DJ Mag*, 2018 [[DM18]](https://djmag.com/content/return-jungle) | feature | F | revival | **CONFIRMED.** Break kick fills **58%** of runtime and two-step 13%. A break kick re-deals its slots from bar to bar (Jaccard 0.29, against 0.53 under a two-step). |

### 1.4 Bass

| # | claim (paraphrased) | source | type | seen | era | verdict and the number |
|---|---|---|---|---|---|---|
| B1 | Jungle's core is breaks at 150+ BPM over a bassline at half that speed (75-80). Dancers follow the slow line while the breaks blur. | Reynolds, 2016 [[AP16]](https://www.afropop.org/articles/first-draft-simon-reynolds-interview); Reynolds, 1994 [[W94]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_2_ambient-jungle_1994_); Christodoulou 2020 (basslines near 80 BPM) [[CH20]](https://dj.dancecult.net/index.php/dancecult/article/view/1153) | interview, essay, academic | F | 1992-95 | **NUANCED.** It is half-time in its *rate*: 1.34 held notes per bar, a median gap of exactly **1.00 beat** between notes (an 8th at half tempo), and 0.90 pitch changes per bar. But it is not a long, legato line. The median note is 0.60 beats, 42% of notes are shorter than an 8th, nothing is held past 1.4 bars, and **41%** of moves are short portamento scoops. |
| B2 | The bass is dub and roots reggae, with a skank to it. Dub bass sits in its own strange metre against the breaks. | Reynolds, 2009 [[EF09]](http://energyflashbysimonreynolds.blogspot.com/2009/02/hardcore-continuum-or-theory-and-its.html); Reynolds, 1992 [[W92]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_1_hardcore-rave_1992_) | essay | F | 1992-95 | **NUANCED.** The key is stable (84.6% of bass time in E♭ minor), but the intervals are not reggae's root-fifth-octave leaps: 34.6% repeated notes, 28.5% steps of 1-2 semitones, 7.4% fifths, 1.8% octaves. It moves stepwise and slides. |
| B3 | Bass is the physical centre: gut-shaking, subsonic, "dark bass pressure", subs that shake the room, cavernous. | Reynolds, 1992 and 2009 [[W92]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_1_hardcore-rave_1992_) [[W09]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_introduction); RBMA Daily, 2016 [[RD16]](https://daily.redbullmusicacademy.com/2016/04/reinforced-interview/); Christodoulou 2020; Dave Jenkins, Bandcamp Daily, 2018 [[BC18]](https://daily.bandcamp.com/lists/best-jungle) | essay, interview, academic, feature | F | all eras | **CONFIRMED, strongly.** **65.6%** of bass power is below 60 Hz, peaking at 40-50 Hz. The low band *is* the dynamic: its share of the spectrum swings from 2% to 26% while per-minute RMS moves only 5.9 dB. A drop is sub +10 dB. |
| B4 | The reese became jungle's bass. Renegade's "Terrorist" (1994) put it on the Amen, reese tracks went from 7 in 1994 to 54 in 1995, and techstep ran it through distortion. Saunderson heard it every three or four records in Fabio & Grooverider's sets. Only the 808 mattered more in the low end. | Marcus Barnes, *Mixmag*, 2025 [[MM25]](https://mixmag.net/feature/kevin-saunderson-reese-bassline-transformed-uk-dance-music-jungle-speed-garage-drum-n-bass); Kevin Saunderson, RBMA, 2018 [[L-KS]](https://www.redbullmusicacademy.com/lectures/kevin-saunderson/); Rihn, 2021 [[BP21]](https://www.beatportal.com/articles/4445-beatports-definitive-history-of-drum-bass) | feature, lecture | F, F\* | 1994-97 | **CONTRADICTED for this set.** It is a **clean sub**: the fundamental is 16.6 dB above the 2nd harmonic, where a reese would put harmonics 2-8 close to the fundamental. The nearest thing is one octave-doubled section (S06). *Era gap*: 1994-95 jungle, then techstep and D&B. |
| B5 | Tim Reaper's music has a bone-shaking reese bass. | Finn Kverndal, *Qobuz Magazine*, Aug 2026 [[QB26]](https://www.qobuz.com/us-en/magazine/story/2026/08/10/jungle-in-10-artists/) | feature | F | revival | **CONTRADICTED in this section** (clean sub, as B4). Caveat: these 9 records are not necessarily his own productions, and a reese in the mid layers would not show up in the sub analysis. |
| B6 | The new jungle's bass comes from pure sine waves. | Joe Rihn, Beatportal, 2020 [[BP20]](https://www.beatportal.com/articles/13807-meet-the-artists-defining-jungles-new-era) | feature | F | revival | **CONFIRMED.** The fundamental is 16.6 dB above h2, and the sub's tone is set per section (it changes about every 17 bars). |
| B7 | The 808 is the low end's sub of choice, and revival jungle mixes sub, 808 and reese. Reinforced's studio had an 808, 909 and 606. | Rihn, 2021 [[BP21]](https://www.beatportal.com/articles/4445-beatports-definitive-history-of-drum-bass); Murphy, 2018 [[DM18]](https://djmag.com/content/return-jungle); RBMA Daily, 2016 [[RD16]](https://daily.redbullmusicacademy.com/2016/04/reinforced-interview/) | feature, interview | F | 1991-now | **NUANCED.** An 808-style pitch drop (+30 semitones, 12 ms time constant) starts **75-94%** of notes in some records and almost none in others. The kick is a separate sound in its own band (its body sits at 60-250 Hz). |
| B8 | Marcus Intalex took the portamento in his basslines from Kevin Saunderson's Detroit bass patterns. | Marcus Intalex, 2003 [[L-MI]](https://www.redbullmusicacademy.com/lectures/marcus-intalex-the-liquidator/) | lecture | F\* | 2000s D&B | **CONFIRMED as a practice.** 41% of note changes are glides (median 96 ms over 0.76 semitones), 2.5 glide runs per bar, and 59% of them fall. |
| B9 | A sine sub and the kick are always fighting, and you deal with it one way or another. | Kode9, RBMA, c. 2010 [[L-K9]](https://www.redbullmusicacademy.com/lectures/kode-9-hypersonics/) *(dubstep, adjacent)* | lecture | F\* | 2000s dubstep | **NUANCED.** The set settles the fight by **register, not ducking**. The dip at the kick is −0.5 dB, and 0 of 14 sections duck by more than 4 dB. The kick puts 42.5% of its energy at 60-250 Hz; the bass puts 73.8% below 60 Hz. |
| B10 | Under the chaotic snares, the bass notes land at regular intervals and give the track its structure. | Christodoulou 2020, on Lemon D's "This Is L.A." [[CH20]](https://dj.dancecult.net/index.php/dancecult/article/view/1153) | academic | F | 1990s | **CONFIRMED.** Riffs loop every 2, 4 or 8 bars and hold for a median 11 bars. Riff changes favour 8-bar lines (33% against 19%), and the low band carries the 4-bar return. |

### 1.5 Tension and release

| # | claim (paraphrased) | source | type | seen | era | verdict and the number |
|---|---|---|---|---|---|---|
| T1 | "Serenity": a high-passed, rearranged Amen plays alone for four bars to tease, then its mids and lows are dropped in, and the heavy sub-bass comes after that. | Christodoulou 2020, observed at the Rupture club, 2019 [[CH20]](https://dj.dancecult.net/index.php/dancecult/article/view/1153) | academic | F | 1990s track, 2019 floor | **CONFIRMED, closely.** **82%** of drops are set up with the break still running and the low end pulled a median **19 dB**. The 16th carrier is mostly a break high-passed at 80-320 Hz, and the sub adds a further +2.1 dB in bar 2. The best single match in the literature. |
| T2 | "This Is L.A.": the melodic layers are pulled, a drum roll builds, then a heavy bass drop lands. | Christodoulou 2020 [[CH20]](https://dj.dancecult.net/index.php/dancecult/article/view/1153) | academic | F | 1990s | **NUANCED.** Pulling layers out is the rule (82% of drops). A roll is the exception (27%), there are zero risers, and only 27% of drops have a gap, a median 80 ms. |
| T3 | The bass drop is the moment that makes the crowd react. At Rupture the crowd answers with the "Bo!" gunshot sign. | Reynolds, 2016 (about dubstep) [[AP16]](https://www.afropop.org/articles/first-draft-simon-reynolds-interview); Christodoulou 2020 | interview, academic | F | continuum | **CONFIRMED.** A drop is a re-weighting toward the bass: sub +10 dB, bass +5 dB, mids −0.9 dB, highs −1.1 dB, centroid −394 Hz, RMS only +2.6 dB. |
| T4 | Hardcore was an endless run of climaxes, one peak after another. | Reynolds, 1992 [[W92]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_1_hardcore-rave_1992_) | essay | F | 1992 | **NUANCED.** There is a peak about every 33 bars, but none is reached by a rise: level typically *falls* 1.3 dB going into a drop. |
| T5 | D&B is punctuated by percussive breakdowns and synth interludes. | Reynolds, 1995 [[W95]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_3_the-state-of-drum_n_bass_1995_) | essay | F | 1995 | **NUANCED.** The breakdowns are percussive: onset density rises in 64% of them, and the centroid rises by 277 Hz. There are no synth interludes: 5 sustained tones in 287 melodic events. |
| T6 | D&B shortened its intros for instant impact, giving up the long build. Two-minute builds became rare. | Zinc, 2005 [[L-ZN]](https://www.redbullmusicacademy.com/lectures/zinc-hardware-bingo/) | lecture | F\* | 2005 D&B | **CONFIRMED.** Everything arrives in bar 1: RMS is within 0.5 dB by bar 2 and onset counts stay flat. The 4 builds last 8-14 bars and take 4.8% of runtime. |
| T7 | Flanging, EQ sweeps and keyboard stabs faded out as production turned toward DJs and beats. | RBMA Daily, 2016 [[RD16]](https://daily.redbullmusicacademy.com/2016/04/reinforced-interview/) | interview | F | 1991-94 | **NUANCED.** They survive as minority devices: filter sweeps before 23% of drops, tonal stabs before 18%. |

### 1.6 From breakbeat jungle to two-step drum & bass

| # | claim (paraphrased) | source | type | seen | era | verdict and the number |
|---|---|---|---|---|---|---|
| S1 | Alex Reece's "Pulp Fiction" brought the two-step beat into the scene, and it went on to dominate neurofunk and UK garage. | Martin James, *The Quietus*, 2020 [[Q20]](https://thequietus.com/articles/28122-state-of-bass-jungle-drum-bass-book-martin-james-playlist) | feature | F | 1995-96 | **NOT MEASURABLE** (history). Note the sources disagree on the date: the record is usually dated 1995, and Beatportal says 1996. |
| S2 | By the 2000s most producers had swapped hyperactive Amen edits for rolling two-step beats in the "Pulp Fiction" mould. | Rihn, Beatportal, 2021 [[BP21]](https://www.beatportal.com/articles/4445-beatports-definitive-history-of-drum-bass) | feature | F | late 90s-2000s | **NUANCED.** True as history, and the revival reverses it: kick runtime is break kick **58%**, sparse/syncopated 26%, two-step **13%**, no kick 4%, four-on-the-floor 0%. |
| S3 | Neurofunk's basic two-step doesn't even sound like a break any more. It is metronomic and asks less of the dancer. | Reynolds, *The Wire* #166, 1997 [[W97]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_5_neurofunk-drum_n_bass-versus-speed) | essay | F | 1997 | **CONFIRMED where it appears.** A two-step repeats (Jaccard 0.53, and 81% of bars within one slot of its usual pattern) against the break kick's 0.29 and 38%. It is one consistent kick sound (timbre distance 9.4 dB against 13.6). |
| S4 | A two-step puts a dominant kick on beats one and three, sparse and repetitive, leaving room for vocals. Break loyalists look down on it. | Christodoulou 2020 [[CH20]](https://dj.dancecult.net/index.php/dancecult/article/view/1153) | academic | F | 2000s-2010s D&B | **NUANCED.** In two-step sections the kick is on slot 0 (0.96-0.98), and its second hit lands *before or on* beat 3 (slot 6 at 0.76-0.80, slot 8 at 0.50). Across the whole set the second kick sits on slot 10 (0.66). Under a two-step the bass barely moves (**0.25** changes per bar against ~1), and the 16th layer thins out (82% none or short percussion). |
| S5 | Hard step ("Special Dedication") brought the kick drum back into ragga jungle. | Martin James, *The Quietus*, 2020 [[Q20]](https://thequietus.com/articles/28122-state-of-bass-jungle-drum-bass-book-martin-james-playlist) | feature | F | 1995 | **NUANCED.** Kicks are present in 96% of runtime, but mostly *inside the break* (58%) rather than as a separate programmed kick. |
| S6 | Mainstream D&B is very two-step now. Storm wants breaks on top of breaks. | DJ Storm, 2018 [[L-ST]](https://www.redbullmusicacademy.com/lectures/dj-storm-lecture/) | lecture | F\* | 2018 D&B | **CONFIRMED as the revival's answer:** 58% break kick against 13% two-step. |
| S7 | After the move into clubs, D&B stripped itself down too far and lost its energy. | dBridge, 2005 [[L-DB]](https://www.redbullmusicacademy.com/lectures/dbridge-many-rivers-to-cross/) | lecture | F\* | mid-late 90s | **NOT MEASURABLE.** |

### 1.7 Hooks, vocals, stabs, pads and space

| # | claim (paraphrased) | source | type | seen | era | verdict and the number |
|---|---|---|---|---|---|---|
| H1 | D&B has no hooks and little melody. It is rhythm-based and monotonous. | Fabio, 2006 [[L-FA]](https://www.redbullmusicacademy.com/lectures/fabio-the-root-to-the-shoot/) | lecture | F\* | 2006 D&B | **NUANCED.** Hooks appear in **39%** of bars, but they are fragments: median **1.2 beats**, 81% under 2 beats, and only 50 of 128 shapes ever recur. There are just 4 lead-line events. |
| H2 | The hooks come from vocal samples, stabs and little string or pizzicato refrains, not from songs. | Reynolds, 2009 [[EF09]](http://energyflashbysimonreynolds.blogspot.com/2009/02/hardcore-continuum-or-theory-and-its.html) | essay | F | 1990s-2000s | **CONFIRMED.** The melodic events break down as 120 riff fragments, 69 stabs, 39 chord stabs, 38 vocal-like, 12 bells, 5 sustained tones and 4 lead lines. |
| H3 | Hardcore's octave-jumping synth riffs were there for texture, not melody. | Reynolds, 1992 [[W92]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_1_hardcore-rave_1992_) | essay | F | 1992 | **NUANCED.** The riffs are short and rarely recur, as texture would be. They sit low (fundamentals **233-392 Hz**) with a 10 dB valley at 233 Hz separating them from the bass. |
| H4 | Ragga jungle peaked in 1994 with reggae samples, dub effects and toasted vocals. Catchphrases like "booyaka" ruled summer 1994. | Rihn, 2021 [[BP21]](https://www.beatportal.com/articles/4445-beatports-definitive-history-of-drum-bass); Martin James, 2020 [[Q20]](https://thequietus.com/articles/28122-state-of-bass-jungle-drum-bass-book-martin-james-playlist); Jenkins, 2018 [[BC18]](https://daily.bandcamp.com/lists/best-jungle); Manu Ekanayake, *The Quietus*, 2026 [[Q26]](https://thequietus.com/quietus-reviews/reissue-of-the-week/ragga-jungle-review/) | feature, review | F | 1993-95 | **NUANCED, partly NOT MEASURABLE.** 38 of 287 melodic events (13%) are vocal-like, and all melodic material together fills only 12% of runtime. Ragga was not classified separately. *Era gap*: this is not a ragga set. |
| H5 | 1995 D&B used abstract vocal samples for mood, with washes of timbre and jazzy chords. | Reynolds, 1995 [[W95]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_3_the-state-of-drum_n_bass_1995_) | essay | F | 1995 | **NUANCED.** The vocal fragments are short, and the washes are missing: only 5 sustained events. |
| H6 | Ambient jungle layered diva vocals, strings, harps and shimmering pads. | Reynolds, 1994 [[W94]](https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_2_ambient-jungle_1994_) | essay | F | 1994 | **CONTRADICTED for this set.** There is no sustained voice in the hook register, and 81% of melodic events last under 2 beats. *Era gap*: 1994 ambient jungle lineage. |
| H7 | Revival jungle has cinematic pads and eerie vocal samples in a sparse arrangement that leaves room around the drums. | Murphy, 2018 [[DM18]](https://djmag.com/content/return-jungle) | feature | F | revival | **NUANCED.** The sparseness is **CONFIRMED**: a drop bar has fewer events than a groove bar (21 against 32 band-onsets), and odd 16ths are 0.34 occupied. The pads are **CONTRADICTED** (5 sustained events). |
| H8 | Beats and bassline come first; melody is the icing on top. | Marcus Intalex, 2003 [[L-MI]](https://www.redbullmusicacademy.com/lectures/marcus-intalex-the-liquidator/) | lecture | F\* | 2000s | **CONFIRMED in proportion.** Hooks fill 12% of runtime, against bass in 76.7% of bars and drums throughout. |
| H9 | Doc Scott is the master of rolling, and of leaving space between sounds. | Goldie, 2008 [[L-GO]](https://www.redbullmusicacademy.com/lectures/goldie-ramblas-in-the-jungle/) | lecture | F\* | 1990s-2000s | **CONFIRMED.** Odd 16ths are left mostly empty (0.34), drop bars carry fewer events, and tails are short but steady (T20 299 ms; 2-8 kHz above −20 dB 96% of the time). |
| H10 | Its dub heritage brings echoed guitar and dub effects. | Christodoulou 2020 [[CH20]](https://dj.dancecult.net/index.php/dancecult/article/view/1153); Rihn, 2021 [[BP21]](https://www.beatportal.com/articles/4445-beatports-definitive-history-of-drum-bass) | academic, feature | F | 1993-94 | **NUANCED.** The echoes are short: an 8th-triplet ~120 ms, an 8th ~181 ms and a 45 ms slapback. Nothing at a quarter note or longer, and no cyclic panning. The dub is in the bass weight, not the delays. |

## 2. What the press gets right, wrong, or never says

### Right

- **Bass is the event.** From Reynolds' 1992 gut-shaking bass to Christodoulou's crowd making the
  gunshot sign when the bass drops, every source puts the drop in the low end. The set agrees: sub +10 dB
  at a drop, with total level up only 2.6 dB. The low band's share swings from 2% to 26% while
  per-minute loudness moves 5.9 dB (B3, T3).
- **The break is chopped and it is the hook.** Reynolds (1995, 2009) and Chapman (via
  Christodoulou) describe breaks rebuilt from fragments, and that is what we measured: slice
  cut-offs 20× locked to the 16th grid, and no bar ever looped (K1-K3). Christodoulou's reading of
  Danielsen (a difference repeated inside the pattern) matches the A-B-C-D bar profile (K5).
- **Pressure, not arcs.** Reynolds' 1996 hardstep plateau (no rises, no dips) and Zinc's
  instant-impact intros describe this set better than the build-and-breakdown story does: full 86% of the time, zero
  risers, builds under 5% (P6, T6).
- **The single best match is academic.** Christodoulou's 2020 account of "Serenity" (a
  high-passed Amen alone for four bars, then the lows let in) is almost exactly the measured
  device: 82% of drops are subtraction with the break running, over a carrier high-passed at
  80-320 Hz (T1).
- **The revival refuses two-step.** Murphy (DJ Mag, 2018) and DJ Storm (2018) say so, and the kick
  runtime backs it: 58% break kick, 13% two-step (K12, S6).
- **The DJ-first form.** Zinc's "comes in after 32 bars" matches the median drop spacing of 33.5
  bars, and Reynolds' pirate-radio mixing of short chunks matches 9 records in 21 minutes (P2, D2).

### Wrong, or wrong for this set

- **"Jungle bass = reese."** Mixmag, Beatportal and Saunderson's lecture tell the reese's history
  accurately, and Qobuz (Aug 2026) applies it to Tim Reaper. The measured low end is a clean sub
  with an 808-style pitch drop on each note (B4, B5, B7). The reese belongs to 1994-95 and then
  techstep; the press lets it stand for the whole genre. Beatportal's 2020 "pure sine waves" line
  is the accurate one (B6).
- **"Half-time dub bassline."** Right about the *rate* (a note about once a beat, a pitch change
  about once a bar), wrong about the *shape*. The line is short notes, stepwise moves and
  portamento scoops, not legato root-fifth reggae phrasing (B1, B2).
- **Build-up, breakdown, drum roll.** Reynolds' 1994 architecture, the hardstep snare roll and
  Christodoulou's Lemon D build all describe devices this set uses rarely: builds 4.8% and
  breakdowns 2.8% of runtime, rolls before 27% of drops, no risers (P5, K11, T2). Some of this is
  the era gap, and some is the DJ cutting breakdowns out.
- **"Breaks play down the strong beats"** (Butler, via Christodoulou). The backbeat is heavily
  marked (snares 0.94 and 0.89, downbeat kick 0.91). The syncopation is layered over it, not a
  replacement for it (K4).
- **Pads, strings, divas, dub echo.** Reynolds (1994, 1995) and Murphy (2018) promise
  atmospheres. The set has 5 sustained melodic events in 21 minutes and no delay as long as a
  quarter note (H5-H7, H10).

### Never says

- **Whether jungle ducks its bass.** No press, history or lecture source we reached says. The set
  doesn't duck (−0.5 dB at the kick) and separates kick and sub by register. The only nearby remark
  is Kode9 on dubstep: the sub and kick fight, and you find a way (B9).
- **The 808 as a per-note pitch drop.** The 808 is named as a kit or a kick, never as the fast
  pitch drop that starts each sub note (B7).
- **How strict the phrase grid is.** Writers and DJs talk in 16s and 32s. Nobody says the grid is
  strictly 4-bar and only loosely 8, or that 16% of sections are an odd number of 4-bar units (P1).
- **Where hooks sit.** No source gives a register. The set puts hooks at 233-392 Hz with a 10 dB
  valley at 233 Hz, which is the actual light-against-dark mechanism (H3).
- **Layer clocks.** Nobody describes riff (~8 bars), sub tone (~17), kick (~28) and carrier (~32)
  running on separate periods and turning over together mostly *inside* records. Tim Reaper comes
  closest when he praises the classic jungle formula for how its parts fit together (Beatportal,
  2020), but he does not spell it out.
- **How the DJ joins records.** Storm and Andy C talk about blends and double drops. Nobody
  describes the two populations measured here (1-5 bar cuts against 8-32 bar blends) or bass
  removal as the handover signal (D1, D3).
- **Call and response inside the bassline.** The press uses "call and response" only for MCs and
  vocals. The measured version, where the second bar of a 2-bar riff sits ~1 semitone lower in 66%
  of cycles, is absent everywhere.
- **Silence.** No fetched source discusses a gap before the drop. The set rarely has one (27% of
  drops, median 80 ms).

### The era gap, in one paragraph

Almost all the structural writing, in The Wire essays, RBMA lectures and Martin James's lists,
describes **1992-97 records** heard whole, or **2000s D&B** that the revival reacts against. Revival
coverage (DJ Mag 2018, Bandcamp Daily 2018, Beatportal 2020, Clash 2024, Crack 2024, Qobuz 2026)
is almost entirely about lineage, labels and "vibe", with nearly nothing about structure. The two
richest structural sources are thirty-year-old criticism and one 2020 academic paper. Where they
disagree with the set, the likeliest reasons are (a) this is a 2026 revival DJ set, not a 1994
record, (b) the DJ cuts intros and breakdowns away, and (c) the press generalises the jungle of its
moment (ragga in 1994, ambient in 1994-95, the reese and techstep in 1995-97) to the whole genre.

### Limits of this search

The session's web-search budget ran out partway through, so the later sources were reached by
direct fetch only. The Guardian and Pitchfork refused automated fetches. RA feature pages render
without a body (the Andy C "Art of DJing" page gave only its title). FACT and Vice/Thump were never
reached. Belle-Fortune's *All Crews* and Eshun's *More Brilliant Than The Sun* are represented only
by search summaries and by other writers' accounts of them. There are no RBMA lecture transcripts
for Photek, Rob Playford, Doc Scott, DJ Hype, LTJ Bukem, Dillinja, Lemon D or Remarc. They appear
here only as the subject of other sources (Goldie on Doc Scott and Playford; Christodoulou on Lemon
D; Martin James on Remarc and Photek), and 4hero only through the RBMA Daily Reinforced interview.

## 3. Sources

**F** fetched and read · **F\*** full text read from a transcript mirror or repost · **2** known
only as cited by a fetched source · **S** search snippet only.

### Essays, features, interviews, reviews

| id | author, title, publication, date | type | seen | URL |
|---|---|---|---|---|
| W92 | Simon Reynolds, hardcore rave essay, *The Wire* #105, Nov 1992 (Wire 300 web reprint) | essay | F | https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_1_hardcore-rave_1992_ |
| W94 | Simon Reynolds, "Ambient Jungle", *The Wire* #127, Sep 1994 | essay | F | https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_2_ambient-jungle_1994_ |
| W95 | Simon Reynolds, "The State Of Drum 'n' Bass", *The Wire* #136, Jun 1995 | essay | F | https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_3_the-state-of-drum_n_bass_1995_ |
| W96 | Simon Reynolds, "Hardstep, Jump Up, Techstep", *The Wire* #148, Jun 1996 | essay | F | https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_4_hardstep_jump-up_techstep_1996_ |
| W97 | Simon Reynolds, "Neurofunk Drum 'n' Bass Versus Speed Garage", *The Wire* #166, Dec 1997 | essay | F | https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_5_neurofunk-drum_n_bass-versus-speed |
| W09 | Simon Reynolds, Hardcore Continuum series introduction, *The Wire* 300, 2009 (web 2013) | essay | F | https://www.thewire.co.uk/in-writing/essays/the-wire-300_simon-reynolds-on-the-hardcore-continuum_introduction |
| EF09 | Simon Reynolds, "The Hardcore Continuum, or (a)Theory and its Discontents", *Energy Flash* blog, Feb 2009 | essay | F | http://energyflashbysimonreynolds.blogspot.com/2009/02/hardcore-continuum-or-theory-and-its.html |
| AP16 | Sam Backer, interview with Simon Reynolds, *Afropop Worldwide*, Jun 2016 | interview | F | https://www.afropop.org/articles/first-draft-simon-reynolds-interview |
| RR | Simon Reynolds, reviews of Eshun's *More Brilliant Than The Sun* (originally the Guardian, late 1990s, and *Groove*, 2008), reposted on his blog, 2013. Used only for context: Eshun's focus on jungle's convoluted breakbeat rhythms. | review | F | http://reynoldsretro.blogspot.com/2013/04/kodwo-eshun-more-brilliant-than-sun.html |
| DM18 | Ben Murphy, "The Return of Jungle", *DJ Mag*, Mar 2018 | feature | F | https://djmag.com/content/return-jungle |
| BC18 | Dave Jenkins, "The Best New Jungle Labels on Bandcamp", Bandcamp Daily, Jan 2018 | feature | F | https://daily.bandcamp.com/lists/best-jungle |
| RD16 | Hanna Bächer, Reinforced Records interview (4hero), RBMA Daily, Apr 2016 | interview | F | https://daily.redbullmusicacademy.com/2016/04/reinforced-interview/ |
| LF15 | Laurent Fintoni, "Wheel It Up: History of the Rewind", *Cuepoint*, Feb 2015 (Medium original returned 403; read on Dub-Stuy's repost) | feature | F\* | https://www.dub-stuy.com/wheel-it-up-history-of-the-rewind/ (original: https://medium.com/cuepoint/wheel-it-up-history-of-the-rewind-21fdcff243d9) |
| Q20 | Martin James, *State of Bass* author's 20 essential D&B tracks, *The Quietus*, Apr 2020 | feature | F | https://thequietus.com/articles/28122-state-of-bass-jungle-drum-bass-book-martin-james-playlist |
| Q26 | Manu Ekanayake, review of *Junglist! Old Skool Ragga, D&B, Jungle 1993-95*, *The Quietus*, Jan 2026 | review | F | https://thequietus.com/quietus-reviews/reissue-of-the-week/ragga-jungle-review/ |
| BP20 | Joe Rihn, "Meet The Artists Defining Jungle's New Era", Beatportal, Oct 2020 (includes Tim Reaper) | feature | F | https://www.beatportal.com/articles/13807-meet-the-artists-defining-jungles-new-era |
| BP21 | Joe Rihn, "Beatport's Definitive History of Drum & Bass", Beatportal, Jul 2021 | feature | F | https://www.beatportal.com/articles/4445-beatports-definitive-history-of-drum-bass |
| MM25 | Marcus Barnes, "How Kevin Saunderson's Reese bassline transformed UK dance music", *Mixmag*, Feb 2025 | feature | F | https://mixmag.net/feature/kevin-saunderson-reese-bassline-transformed-uk-dance-music-jungle-speed-garage-drum-n-bass |
| QB26 | Finn Kverndal, "Jungle in 10 Artists", *Qobuz Magazine*, Aug 2026 | feature | F | https://www.qobuz.com/us-en/magazine/story/2026/08/10/jungle-in-10-artists/ |
| SK16 | Becca Frankland, "Andy C interview: Double drop", Skiddle, 2016 | interview | F | https://www.skiddle.com/news/all/Andy-C-interview-Double-drop/28832/ |
| CR24 | "SHERELLE in conversation with Tim Reaper", *Crack Magazine*, Nov 2024. Culture and lineage only; no structural claims used. | interview | F | https://crackmagazine.net/article/long-reads/sherelle-in-conversation-with-tim-reaper/ |
| CL24 | Harvey Marwood, "Seven Jungle Artists Carrying The Torch For The NewGen", *Clash*, May 2024. Generic; no structural claims used. | feature | F | https://www.clashmusic.com/features/seven-jungle-artists-carrying-the-torch-for-the-new-gen/ |
| UKF | Ant Mulholland, "In Conversation With Tim Reaper", UKF, undated. Vinyl mixing and lineage only; no structural claims used. | interview | F | https://ukf.com/read/in-conversation-with-tim-reaper-2/ |
| IR20 | Ellie Jones, interview with Martin James, *In-Reach*, Apr 2020. Cultural history; one line on cut-and-splice breakbeats. | interview | F | https://in-reach.co.uk/interview-with-martin-james-author-of-state-of-bass-the-origins-of-jungle-drum-bass-2/ |
| VP20 | Velocity Press, "The story of State of Bass" (2020 reissue page). Framing only. | feature | F | https://velocitypress.uk/story-of-state-of-bass-book/ |
| CD13 | Bob Baker Fish, review of *Energy Flash*, *Cyclic Defrost*, Sep 2013. Nothing on jungle's structure. | review | F | https://www.cyclicdefrost.com/2013/09/energy-flash-a-journey-through-rave-music-dance-culture-simon-reynolds-faber-allen-unwin/ |
| RA18 | Dave Herringbone, "The art of DJing: Andy C", *Resident Advisor*, May 2018. The page rendered without its body. | feature | S (title only) | https://ra.co/features/3218 |
| DA14 | "All hail the executioner: Andy C...", *Dancing Astronaut*, Jan 2014 (Andy C coined the double drop) | feature | S | https://dancingastronaut.com/2014/01/all-hail-the-executioner-andy-c-and-the-absolution-of-drum-and-bass/ |

### Lectures (Red Bull Music Academy)

All were read in full from the plain-text transcript mirror at
https://github.com/ewenme/rbma-lectures (`data/<slug>.txt`). The Goldie, DJ Storm and Digital
lecture URLs came up in search results. The rest are built from the mirror's slug, which follows the
RBMA URL pattern, and were not opened.

| id | speaker, lecture, year | seen | URL |
|---|---|---|---|
| L-MI | Marcus Intalex, "The Liquidator", RBMA 2003 | F\* | https://www.redbullmusicacademy.com/lectures/marcus-intalex-the-liquidator/ |
| L-TC | Tony Colman (London Elektricity / Hospital), "Gravytrain", RBMA 2003 | F\* | https://www.redbullmusicacademy.com/lectures/tony-colman-gravytrain/ |
| L-DG | Digital, "Roots Rocker", RBMA 2004 | F\* | https://www.redbullmusicacademy.com/lectures/digital-roots-rocker/ |
| L-DB | dBridge, "Many Rivers To Cross", RBMA 2005 | F\* | https://www.redbullmusicacademy.com/lectures/dbridge-many-rivers-to-cross/ |
| L-ZN | Zinc, "Hardware Bingo", RBMA 2005 | F\* | https://www.redbullmusicacademy.com/lectures/zinc-hardware-bingo/ |
| L-FA | Fabio, "The Root To The Shoot", RBMA 2006 | F\* | https://www.redbullmusicacademy.com/lectures/fabio-the-root-to-the-shoot/ |
| L-GO | Goldie, "Ramblas In The Jungle", RBMA 2008 | F\* | https://www.redbullmusicacademy.com/lectures/goldie-ramblas-in-the-jungle/ |
| L-K9 | Kode9, "Hypersonics", RBMA c. 2010 (dubstep, adjacent) | F\* | https://www.redbullmusicacademy.com/lectures/kode-9-hypersonics/ |
| L-ST | DJ Storm (Kemistry & Storm), public talk at CTM / RBMA Berlin, 2018 | F\* | https://www.redbullmusicacademy.com/lectures/dj-storm-lecture/ |
| L-KS | Kevin Saunderson, RBMA Berlin, 2018 | F\* | https://www.redbullmusicacademy.com/lectures/kevin-saunderson/ |

### Academic and books

| id | work | type | seen | URL |
|---|---|---|---|---|
| CH20 | Chris Christodoulou, "Bring the Break-Beat Back! Authenticity and the Politics of Rhythm in Drum 'n' Bass", *Dancecult* 12(1): 3-21, 2020. Full PDF read. | academic | F | https://dj.dancecult.net/index.php/dancecult/article/view/1153 (PDF: https://dj.dancecult.net/index.php/dancecult/article/download/1153/1003/4507) |
| — | Mark J. Butler, *Unlocking the Groove*, Indiana UP, 2006 | academic | 2 (via CH20) | — |
| — | Anne Danielsen, *Presence and Pleasure*, Wesleyan UP, 2006 | academic | 2 (via CH20) | — |
| — | Dale Chapman, "Hermeneutics of Suspicion", *Echo* 5(2), 2003. Direct fetch failed on a certificate error. | academic | 2 (via CH20) | http://www.echo.ucla.edu/volume5-issue2/chapman/chapman.pdf |
| — | Martin James, *State of Bass: Jungle, the Story So Far*, Boxtree, 1997 (the Omni Trio "sequenced music" line) | book | 2 (via CH20) | https://velocitypress.uk/story-of-state-of-bass-book/ |
| — | Brian Belle-Fortune, *All Crews: Journeys Through Jungle / Drum & Bass Culture*, 1999/2004. Only cultural summaries seen (dubplates, pirates, raves); no structural claims found. | book | S | https://en.wikipedia.org/wiki/All_Crews |
| — | Kodwo Eshun, *More Brilliant Than The Sun*, Quartet, 1998. Seen only through search summaries, Reynolds' review (RR) and Beatportal's use of his "hyperrhythm" idea (BP21). | book | S / 2 | https://books.google.com/books/about/More_Brilliant_Than_the_Sun.html?id=VhBEAQAAIAAJ |
| — | Chris Christodoulou, "Speed Limits: Accelerationism, Popular Futurism and the Decline of Jungle Drum and Bass". Repository page refused the fetch; title only. | academic | S | https://westminsterresearch.westminster.ac.uk/item/wz0zw/speed-limits-accelerationism-popular-futurism-and-the-decline-of-jungle-drum-and-bass |
