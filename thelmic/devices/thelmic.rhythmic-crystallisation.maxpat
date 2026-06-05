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
      1000,
      680
    ],
    "openinpresentation": 0,
    "boxes": [
      {
        "box": {
          "maxclass": "comment",
          "text": "Pulse Field — Stage 1: RHYTHMIC CRYSTALLISATION",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            10,
            460,
            20
          ],
          "id": "obj-1"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "field in via LOM observe or inlet feed; MIDI out below",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            30,
            460,
            20
          ],
          "id": "obj-2"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "js rhythmic-crystallisation.js",
          "numinlets": 1,
          "numoutlets": 2,
          "patching_rect": [
            20,
            120,
            220,
            22
          ],
          "outlettype": [
            "",
            ""
          ],
          "saved_object_attributes": {
            "filename": "rhythmic-crystallisation.js",
            "parameter_enable": 0
          },
          "id": "obj-3"
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
            20,
            56,
            24,
            24
          ],
          "id": "obj-4"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "metro 5",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            20,
            84,
            70,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-5"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "on/off  -> 5ms tick clock",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            50,
            58,
            220,
            20
          ],
          "id": "obj-6"
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
            160,
            130,
            22
          ],
          "outlettype": [
            "",
            "",
            ""
          ],
          "id": "obj-7"
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
            200,
            130,
            22
          ],
          "outlettype": [
            "",
            ""
          ],
          "id": "obj-8"
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
            240,
            70,
            22
          ],
          "id": "obj-9"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "print crystal",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            260,
            160,
            100,
            22
          ],
          "id": "obj-10"
        }
      }
    ],
    "lines": [
      {
        "patchline": {
          "source": [
            "obj-4",
            0
          ],
          "destination": [
            "obj-5",
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
            "obj-3",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-3",
            0
          ],
          "destination": [
            "obj-7",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-7",
            0
          ],
          "destination": [
            "obj-8",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-7",
            1
          ],
          "destination": [
            "obj-8",
            1
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-7",
            2
          ],
          "destination": [
            "obj-8",
            2
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
            "obj-8",
            1
          ],
          "destination": [
            "obj-9",
            1
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-3",
            1
          ],
          "destination": [
            "obj-10",
            0
          ]
        }
      }
    ]
  }
}