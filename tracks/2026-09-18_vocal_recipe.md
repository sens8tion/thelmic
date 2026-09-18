# Making a sung hook that survives a jungle mix

Measured on 2026-09-17/18 with `thelmic.sources.vocal` (TIGER DS v106, DiffSinger), on the GPU with
the user's permission. Every claim here is a measurement, not an impression: legibility is the word
error rate from a blind transcriber over 6-10 takes a config, because the model has no seed and a
single take proves nothing. Tools: `local-sung-vocals/bench/sweep_hook.py`, `diag_emphasis.py`,
`scripts/jungle_vocal_takes.py`.

## The recipe

| Decision | Setting | Evidence |
|---|---|---|
| Voice | **tiger_glam** | 6/6 takes legible, against 2/6 for tiger_electric |
| Tempo | **render at half tempo, warp onto the grid** | words fill 90-95% of their slots, against 60-70% |
| Register | **root E4 (64) or below** | 6/6 at every root from D3 to E4; 2/6 at G#4 |
| Lead word | **as long as the word is.** Two-syllable and open words 0.7 beats or more; **percussive words short** (0.35-0.4 beats, ~110 ms once warped) | the 0.7 rule came from "bubble"; for "hop" 0.35 beats scored the same as 1.25. Longer made the user hear sung vowels where the word is a hit |
| Ornaments | **a scoop, any depth from -0.6 to -2.4 st** | 6/6 with, 4/6 without |
| Emphasis | **velocity 0.9 on the stressed word** | 6/6 and brighter; gender costs legibility at every setting |
| Consonant caps | **leave them alone** | default 6/6; looser 4/6, tighter 5/6 |
| Diffusion steps | **8 is as good as 70** | no measurable difference; cost is linear in steps |
| Level balance | **after the render** | the bank has no energy input; `scripts/jungle_vocal_emphasis.py` |

## Writing the words

- **A held word must end open.** Plosive endings die on a sustain (1 in 5 survive). "roll", "flow",
  "bubble" hold; "break", "light", "wake" do not.
- **Don't put near-identical words together.** "lick like this" cannot be rendered: across 10
  variants x 8 takes - longer lead, different vowel, three voices, with and without "it", explicit
  closure, a gap after the k - **zero** takes were legible. The model sings the second word and
  swallows the first, and the transcriber hears "leg it", "click", "link". Nothing fixed it.
- **Dictionary entries carry a trailing stop closure** (`hop` is `hh ao p cl`). At the end of a
  phrase that closure sounds as a voiced "uh". Write stop-final words with explicit phonemes and no
  `cl`.
- **Score a phrase the way it is said.** "bump to the mix" with "bump" on its own and "to the mix"
  as a pickup: "to" heard as "you", "who's", "do" in 11 of 12 takes, at any length. Run together
  as spoken: 6 of 6, and the first fully legible take. The t needs the word before it.
- **An unvoiced ending can grow a vowel.** "mix" came back as "mixer" in most takes: ~90 ms of
  low, voiced sound after the s. Making it short made it worse (0 of 6). Cut it off instead: end
  the chop where the hiss ends. Trimmed, the transcriber heard "bump to the mix".
- **Check the inferred pronunciations.** The bank's dictionary is an override set, so ordinary words
  come from CMUdict: "hop" arrives as `hh aa p`, an American vowel that is heard as "hope". Every
  render prints them and `Sound.extra["inferred_pronunciations"]` carries them.

## Chopping onto pads

- **Cut from where the word starts sounding, not from its note.** The renderer puts a leading
  consonant *before* the note so the vowel lands on the beat; cutting at the note took the "n" off
  "now" (heard as "ow") and the start off six chops. Walk back from the word's first sound to the
  silence before it, or, where words run together, to the dip between them. End before the next
  word's consonant for the same reason. (`scripts/jungle_vocal_chops.py`, `tighten`)
- **A word sung as a swell loses its consonant on a pad.** "now" (expr 1.0, a scoop, the call's
  high note) starts 27 dB under its own peak and takes 270 ms to come within 6 dB; the other
  consonant-led chops start 6-17 dB under and get there in 10-90 ms. Inside its phrase it reads;
  hit on its own over drums, only the swell is heard. Lift the onset (12 dB, ramped away over
  200 ms) to put it beside the others.
- **The 2x squeeze costs short words.** As sung, "to the mix" and "bump to the mix" were heard
  exactly; squeezed to 170 with WSOLA, "to the next" and "come on to the next" - as "bump, ooh"
  was before. That's what the two kits (MOUTH-OFF squeezed, BIG-MOUTH as sung) are for.
- **The transcriber can't judge a chop.** It heard "No, no, no" from three "now"s with and without
  the n. The user's ear is the measure for anything under a phrase.

## Shape, from the reference track

Hooks in the reference (tracks/2026-09-16_reaper/hooks.md) are short - a median 1.2 beats - sit in
the low mids, and appear in about 4 bars in 10, leaving room for the bass to answer. So: one phrase
a bar, landing by beat 3, with the fourth bar left to the sub. That is what
`tracks/vocals/hook-4bar-85bpm-011757.wav` does.

## What is still open

- **Whether warping costs legibility.** Everything here is measured before the 2x warp onto the
  grid. Live's Complex Pro cannot be run offline, so this needs measuring inside Live.
- **Why negative gender destroys a word** while positive only colours it. Measured, not explained.
- **Whether a human hears what the transcriber hears.** On phrases of 2-3 seconds the transcriber's
  language model invents whole sentences ("link in the description"), so WER is only trustworthy
  on longer lines. The user's ear caught a fault (gender +0.2 blurring a word) that every spectral
  measure called free.
