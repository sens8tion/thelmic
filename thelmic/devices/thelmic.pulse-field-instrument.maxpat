{
  "patcher": {
    "fileversion": 1,
    "appversion": {
      "major": 8,
      "minor": 5,
      "revision": 5,
      "architecture": "x64",
      "modernui": 1
    },
    "classnamespace": "box",
    "rect": [
      100,
      100,
      640,
      460
    ],
    "openinpresentation": 0,
    "boxes": [
      {
        "box": {
          "maxclass": "comment",
          "text": "Pulse Field — INSTRUMENT (field + crystallisation in one device)",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            8,
            600,
            20
          ],
          "id": "obj-1"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "OSC in on 7400 -> MIDI onsets out. Feed with examples/pulse_field_drive.py",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            26,
            600,
            20
          ],
          "id": "obj-2"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "udpreceive 7400",
          "numinlets": 0,
          "numoutlets": 1,
          "patching_rect": [
            20,
            60,
            170,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-3"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "js thelmic.pulse-field-instrument.bundle.js",
          "numinlets": 1,
          "numoutlets": 2,
          "patching_rect": [
            20,
            100,
            280,
            22
          ],
          "outlettype": [
            "",
            ""
          ],
          "saved_object_attributes": {
            "filename": "thelmic.pulse-field-instrument.bundle.js",
            "parameter_enable": 0
          },
          "id": "obj-4"
        }
      },
      {
        "box": {
          "maxclass": "toggle",
          "numinlets": 1,
          "numoutlets": 1,
          "outlettype": [
            "int"
          ],
          "patching_rect": [
            330,
            60,
            24,
            24
          ],
          "id": "obj-5"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "metro 5",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            360,
            60,
            70,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-6"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "on -> 5ms onset clock",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            330,
            40,
            220,
            20
          ],
          "id": "obj-7"
        }
      },
      {
        "box": {
          "maxclass": "toggle",
          "numinlets": 1,
          "numoutlets": 1,
          "outlettype": [
            "int"
          ],
          "patching_rect": [
            470,
            60,
            24,
            24
          ],
          "id": "obj-8"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend freeze",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            470,
            88,
            110,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-9"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "freeze field",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            500,
            40,
            100,
            20
          ],
          "id": "obj-10"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "unpack i i i",
          "numinlets": 1,
          "numoutlets": 3,
          "patching_rect": [
            20,
            150,
            130,
            22
          ],
          "outlettype": [
            "",
            "",
            ""
          ],
          "id": "obj-11"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "makenote 100 200",
          "numinlets": 3,
          "numoutlets": 2,
          "patching_rect": [
            20,
            190,
            130,
            22
          ],
          "outlettype": [
            "",
            ""
          ],
          "id": "obj-12"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "noteout",
          "numinlets": 2,
          "numoutlets": 0,
          "patching_rect": [
            20,
            230,
            70,
            22
          ],
          "id": "obj-13"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "print pulsefield",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            320,
            150,
            120,
            22
          ],
          "id": "obj-14"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "In Live: Max MIDI Effect -> this device -> Drum Rack. Turn on the clock toggle.",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            270,
            600,
            20
          ],
          "id": "obj-15"
        }
      }
    ],
    "lines": [
      {
        "patchline": {
          "source": [
            "obj-3",
            0
          ],
          "destination": [
            "obj-4",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-5",
            0
          ],
          "destination": [
            "obj-6",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-6",
            0
          ],
          "destination": [
            "obj-4",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-8",
            0
          ],
          "destination": [
            "obj-9",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-9",
            0
          ],
          "destination": [
            "obj-4",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-4",
            0
          ],
          "destination": [
            "obj-11",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-11",
            0
          ],
          "destination": [
            "obj-12",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-11",
            1
          ],
          "destination": [
            "obj-12",
            1
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-11",
            2
          ],
          "destination": [
            "obj-12",
            2
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-12",
            0
          ],
          "destination": [
            "obj-13",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-12",
            1
          ],
          "destination": [
            "obj-13",
            1
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-4",
            1
          ],
          "destination": [
            "obj-14",
            0
          ]
        }
      }
    ]
  }
}