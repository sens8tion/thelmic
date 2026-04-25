"""Phase 1 acceptance test: kick drum output to virtual MIDI port.

Run this, open Ableton (or any DAW), select 'thelmic' as MIDI input.
You should hear kick drum patterns that shift character as landscape_position changes.

Usage:
    python examples/kick_only.py [--position 0.0-1.0] [--bpm 174] [--banks 4]
"""

import argparse

from thelmic.bank_generator import BankGenerator
from thelmic.controls import Controls
from thelmic.force_engine import ForceEngine
from thelmic.midi_out import MIDIOut


def main() -> None:
    parser = argparse.ArgumentParser(description="Thelmic kick-only demo")
    parser.add_argument("--position", type=float, default=0.0,
                        help="Landscape position 0.0 (Oak) to 1.0 (Nott)")
    parser.add_argument("--bpm", type=float, default=174.0)
    parser.add_argument("--banks", type=int, default=4,
                        help="Number of banks to play")
    args = parser.parse_args()

    engine = ForceEngine(landscape_position=args.position)
    controls = Controls()
    generator = BankGenerator(controls=controls)

    print(f"thelmic — kick only")
    print(f"position={args.position:.2f}  territory={_territory(args.position)}")
    print(f"force state: {engine.force_state}")
    print(f"bpm={args.bpm}  banks={args.banks}")
    print()
    print("Opening MIDI port 'thelmic'... (connect in your DAW now)")

    with MIDIOut() as midi:
        print("Port open. Playing...")
        for bank_idx in range(args.banks):
            snapshot = engine.begin_bank()
            bank = generator.generate(engine.force_state, bank_idx)
            print(f"  bank {bank_idx + 1}/{args.banks}  events={len(bank.all_events())}")
            midi.play_bank_blocking(bank, bpm=args.bpm)
            engine.commit_bank(snapshot)

    print("Done.")


def _territory(pos: float) -> str:
    if pos < 0.33:
        return "Oak"
    if pos < 0.67:
        return "Chaos"
    return "Nott"


if __name__ == "__main__":
    main()
