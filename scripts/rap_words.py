"""RAP WORDS - what each audition vocal says, line by line, with where it sits in the clip.

Runs under local-sung-vocals' venv, which has faster-whisper and its cached models:

    ..\\local-sung-vocals\\.venv\\Scripts\\python.exe scripts/rap_words.py [--model base]

Transcribes the ORIGINAL downloads (the stretch would only blur them) with word timestamps, then
moves every time onto the clip as it plays in the set - stretched to 170 or 85 - and gives it in
beats, so a phrase can be found and chopped. Language is detected per clip; translation is done
afterwards, by hand, into the words sheet.

A transcriber is a guesser on rap: it hears slang as dictionary words and invents lines in the
gaps (it did on the sung calls: "link in the description"). Treat every line as "heard as".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from rap_audition import LANES, LABELS, SRC, source_bpm, target_bpm  # noqa: E402

LSV = REPO.parent / "local-sung-vocals"
OUT = REPO / "tracks" / "2026-09-18_rap_audition_words.json"
# Left to detect the language, the base model took a DnB MC for Spanish, patois for Italian and a
# Brazilian funk MC for English. Each track's language is known: say so.
LANE_LANGUAGE = {"BARS-OF-SOAP": "en", "SHOUT-OUT": "en", "FALA-SERIO": "pt"}


def main(model_name: str = "base") -> None:
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="cpu", compute_type="int8",
                         download_root=str(LSV / "tools" / "_whisper"))
    sheet = {}
    for lane, files in LANES.items():
        for name in files:
            bpm = source_bpm(name)
            tempo = target_bpm(bpm) if bpm else None
            scale = (bpm / tempo) if bpm else 1.0            # original seconds -> clip seconds
            beats_per_s = (tempo or 170.0) / 60.0
            segs, info = model.transcribe(str(SRC / name), word_timestamps=True, vad_filter=False,
                                          language=LANE_LANGUAGE.get(lane),
                                          beam_size=5, condition_on_previous_text=False)
            lines = []
            for s in segs:
                words = [{"w": w.word.strip(), "beat": round(w.start * scale * beats_per_s, 2),
                          "end": round(w.end * scale * beats_per_s, 2),
                          "p": round(w.probability, 2)} for w in (s.words or [])]
                lines.append({"beat": round(s.start * scale * beats_per_s, 2),
                              "end": round(s.end * scale * beats_per_s, 2),
                              "text": s.text.strip(), "words": words,
                              "p": round(sum(w["p"] for w in words) / max(1, len(words)), 2)})
            sheet[name] = {"track": lane, "clip": LABELS[name], "tempo": tempo,
                           "language": info.language, "language_p": round(info.language_probability, 2),
                           "lines": lines}
            print(f"  {lane:<13} {LABELS[name]:<18} [{info.language} {info.language_probability:.2f}] "
                  + " / ".join(l["text"] for l in lines)[:150], flush=True)
    OUT.write_text(json.dumps({"model": model_name, "clips": sheet}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(args[args.index("--model") + 1] if "--model" in args else "base")
