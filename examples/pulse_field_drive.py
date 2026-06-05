"""Drive the Pulse Field devices over OSC by walking the landscape.

Walks a trajectory Oak -> Chaos -> Nott -> Oak, mapping each position to a
field vector and streaming it to the Stage 0 Field State device on UDP 7400.
Run the combined test patch (thelmic/devices/thelmic.pulse-field-test.maxpat)
or the Stage 0 device in Live to receive it.

    python -m examples.pulse_field_drive            # full loop
    python -m examples.pulse_field_drive --once     # one pass, then stop
    python -m examples.pulse_field_drive --host 192.168.1.5 --port 7400

Naming is deliberately plain here because this is a dev harness, not a track.
"""

from __future__ import annotations

import argparse
import time

from thelmic.landscape_map import ANCHORS
from thelmic.pulse_field import DIMENSION_NAMES, FieldDriver, OSCSender, nearest_territory


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def waypoints():
    return [ANCHORS["oak"], ANCHORS["chaos"], ANCHORS["nott"], ANCHORS["oak"]]


def main() -> None:
    ap = argparse.ArgumentParser(description="Pulse Field OSC driver")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7400)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--steps", type=int, default=120, help="steps per leg")
    ap.add_argument("--rate", type=float, default=30.0, help="updates/sec")
    ap.add_argument("--once", action="store_true", help="single pass then exit")
    args = ap.parse_args()

    driver = FieldDriver(seed=args.seed)
    sender = OSCSender(host=args.host, port=args.port)
    dt = 1.0 / args.rate
    legs = waypoints()

    print(f"driving Pulse Field -> {args.host}:{args.port}  (Ctrl-C to stop)")
    try:
        while True:
            for i in range(len(legs) - 1):
                a, b = legs[i], legs[i + 1]
                for s in range(args.steps):
                    x, y = lerp(a, b, s / max(1, args.steps - 1))
                    field = driver.update(x, y)
                    # whole-vector blob in canonical order
                    sender.send("/thelmic/field", *field.as_tuple())
                    terr, conf = nearest_territory(field)
                    bars = " ".join(
                        f"{n[:3]}:{getattr(field, n):.2f}" for n in DIMENSION_NAMES
                    )
                    print(f"\r[{terr:>5} {conf:.2f}] {bars}", end="", flush=True)
                    time.sleep(dt)
            if args.once:
                break
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        sender.close()


if __name__ == "__main__":
    main()
