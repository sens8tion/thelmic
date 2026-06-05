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
          "text": "Pulse Field — Stage 2: TEXTURE / ATMOSPHERE",
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
          "maxclass": "newobj",
          "text": "js texture.js",
          "numinlets": 1,
          "numoutlets": 11,
          "patching_rect": [
            20,
            90,
            160,
            22
          ],
          "outlettype": [
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            ""
          ],
          "saved_object_attributes": {
            "filename": "texture.js",
            "parameter_enable": 0
          },
          "id": "obj-2"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "metro 20 -> message 'tick' -> [js texture.js]",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            60,
            400,
            20
          ],
          "id": "obj-3"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "line~",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            20,
            140,
            80,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-4"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "sub_freq -> [line~] -> audio graph",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            110,
            140,
            320,
            20
          ],
          "id": "obj-5"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "line~",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            20,
            166,
            80,
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
          "text": "sub_level -> [line~] -> audio graph",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            110,
            166,
            320,
            20
          ],
          "id": "obj-7"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "line~",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            20,
            192,
            80,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-8"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "mid_freq -> [line~] -> audio graph",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            110,
            192,
            320,
            20
          ],
          "id": "obj-9"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "line~",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            20,
            218,
            80,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-10"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "mid_bw -> [line~] -> audio graph",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            110,
            218,
            320,
            20
          ],
          "id": "obj-11"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "line~",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            20,
            244,
            80,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-12"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "mid_q -> [line~] -> audio graph",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            110,
            244,
            320,
            20
          ],
          "id": "obj-13"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "line~",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            20,
            270,
            80,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-14"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "mid_level -> [line~] -> audio graph",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            110,
            270,
            320,
            20
          ],
          "id": "obj-15"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "line~",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            20,
            296,
            80,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-16"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "air_freq -> [line~] -> audio graph",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            110,
            296,
            320,
            20
          ],
          "id": "obj-17"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "line~",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            20,
            322,
            80,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-18"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "air_level -> [line~] -> audio graph",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            110,
            322,
            320,
            20
          ],
          "id": "obj-19"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "line~",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            20,
            348,
            80,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-20"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "drive -> [line~] -> audio graph",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            110,
            348,
            320,
            20
          ],
          "id": "obj-21"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "line~",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            20,
            374,
            80,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-22"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "master -> [line~] -> audio graph",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            110,
            374,
            320,
            20
          ],
          "id": "obj-23"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "line~",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            20,
            400,
            80,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-24"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "evo_ms -> [line~] -> audio graph",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            110,
            400,
            320,
            20
          ],
          "id": "obj-25"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "AUDIO GRAPH (build by hand — see README Stage 2):",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            440,
            460,
            20
          ],
          "id": "obj-26"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "noise~ -> svf~ (sub) ; noise~ -> reson~ (mid, freq/Q) ; noise~ -> hip~ (air)",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            460,
            600,
            20
          ],
          "id": "obj-27"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "mix by *~ sub_level/mid_level/air_level ; overdrive~ by drive ; *~ master -> plugout~",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            480,
            640,
            20
          ],
          "id": "obj-28"
        }
      }
    ],
    "lines": [
      {
        "patchline": {
          "source": [
            "obj-2",
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
            "obj-2",
            1
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
            "obj-2",
            2
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
            "obj-2",
            3
          ],
          "destination": [
            "obj-10",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-2",
            4
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
            "obj-2",
            5
          ],
          "destination": [
            "obj-14",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-2",
            6
          ],
          "destination": [
            "obj-16",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-2",
            7
          ],
          "destination": [
            "obj-18",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-2",
            8
          ],
          "destination": [
            "obj-20",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-2",
            9
          ],
          "destination": [
            "obj-22",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-2",
            10
          ],
          "destination": [
            "obj-24",
            0
          ]
        }
      }
    ]
  }
}