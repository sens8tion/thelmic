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
      60,
      60,
      1180,
      720
    ],
    "openinpresentation": 0,
    "boxes": [
      {
        "box": {
          "maxclass": "comment",
          "text": "Pulse Field — COMBINED TEST (Stage 0 -> 1 + 3, no Live needed)",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            8,
            700,
            20
          ],
          "id": "obj-1"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "Drag the sliders to drive the field; watch the monitor + MIDI print.",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            26,
            700,
            20
          ],
          "id": "obj-2"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "js field-state.js",
          "numinlets": 1,
          "numoutlets": 10,
          "patching_rect": [
            20,
            300,
            150,
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
            ""
          ],
          "saved_object_attributes": {
            "filename": "field-state.js",
            "parameter_enable": 0
          },
          "id": "obj-3"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "udpreceive 7400",
          "numinlets": 0,
          "numoutlets": 1,
          "patching_rect": [
            200,
            300,
            150,
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
          "maxclass": "live.slider",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "test_pressure",
          "patching_rect": [
            20,
            60,
            36,
            120
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "test_pressure",
              "parameter_shortname": "test_pressure",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-5"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend pressure",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            20,
            190,
            90,
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
          "text": "pressu",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            44,
            60,
            20
          ],
          "id": "obj-7"
        }
      },
      {
        "box": {
          "maxclass": "live.slider",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "test_stability",
          "patching_rect": [
            90,
            60,
            36,
            120
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "test_stability",
              "parameter_shortname": "test_stability",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-8"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend stability",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            90,
            190,
            90,
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
          "text": "stabil",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            90,
            44,
            60,
            20
          ],
          "id": "obj-10"
        }
      },
      {
        "box": {
          "maxclass": "live.slider",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "test_density",
          "patching_rect": [
            160,
            60,
            36,
            120
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "test_density",
              "parameter_shortname": "test_density",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-11"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend density",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            160,
            190,
            90,
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
          "text": "densit",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            160,
            44,
            60,
            20
          ],
          "id": "obj-13"
        }
      },
      {
        "box": {
          "maxclass": "live.slider",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "test_discomfort",
          "patching_rect": [
            230,
            60,
            36,
            120
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "test_discomfort",
              "parameter_shortname": "test_discomfort",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-14"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend discomfort",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            230,
            190,
            90,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-15"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "discom",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            230,
            44,
            60,
            20
          ],
          "id": "obj-16"
        }
      },
      {
        "box": {
          "maxclass": "live.slider",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "test_silence",
          "patching_rect": [
            300,
            60,
            36,
            120
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "test_silence",
              "parameter_shortname": "test_silence",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-17"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend silence",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            300,
            190,
            90,
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
          "text": "silenc",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            300,
            44,
            60,
            20
          ],
          "id": "obj-19"
        }
      },
      {
        "box": {
          "maxclass": "live.slider",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "test_novelty",
          "patching_rect": [
            370,
            60,
            36,
            120
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "test_novelty",
              "parameter_shortname": "test_novelty",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-20"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend novelty",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            370,
            190,
            90,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-21"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "novelt",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            370,
            44,
            60,
            20
          ],
          "id": "obj-22"
        }
      },
      {
        "box": {
          "maxclass": "live.slider",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "test_urgency",
          "patching_rect": [
            440,
            60,
            36,
            120
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "test_urgency",
              "parameter_shortname": "test_urgency",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-23"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend urgency",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            440,
            190,
            90,
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
          "text": "urgenc",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            440,
            44,
            60,
            20
          ],
          "id": "obj-25"
        }
      },
      {
        "box": {
          "maxclass": "live.slider",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "test_momentum",
          "patching_rect": [
            510,
            60,
            36,
            120
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "test_momentum",
              "parameter_shortname": "test_momentum",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-26"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend momentum",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            510,
            190,
            90,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-27"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "moment",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            510,
            44,
            60,
            20
          ],
          "id": "obj-28"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "pak f f f f f f f f",
          "numinlets": 8,
          "numoutlets": 1,
          "patching_rect": [
            20,
            360,
            240,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-29"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend field",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            20,
            392,
            100,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-30"
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
            470,
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
          "id": "obj-31"
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
            300,
            430,
            24,
            24
          ],
          "id": "obj-32"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "metro 5",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            330,
            430,
            70,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-33"
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
            510,
            130,
            22
          ],
          "outlettype": [
            "",
            "",
            ""
          ],
          "id": "obj-34"
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
            545,
            130,
            22
          ],
          "outlettype": [
            "",
            ""
          ],
          "id": "obj-35"
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
            580,
            70,
            22
          ],
          "id": "obj-36"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "print onset",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            260,
            510,
            100,
            22
          ],
          "id": "obj-37"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "js monitor.js",
          "numinlets": 1,
          "numoutlets": 3,
          "patching_rect": [
            460,
            470,
            140,
            22
          ],
          "outlettype": [
            "",
            "",
            ""
          ],
          "saved_object_attributes": {
            "filename": "monitor.js",
            "parameter_enable": 0
          },
          "id": "obj-38"
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
            620,
            440,
            24,
            24
          ],
          "id": "obj-39"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "metro 16",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            650,
            440,
            70,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-40"
        }
      },
      {
        "box": {
          "maxclass": "jsui",
          "numinlets": 1,
          "numoutlets": 1,
          "outlettype": [
            ""
          ],
          "patching_rect": [
            460,
            510,
            520,
            180
          ],
          "saved_object_attributes": {
            "filename": "monitor-ui.js",
            "parameter_enable": 0
          },
          "id": "obj-41"
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
            "obj-3",
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
            "obj-3",
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
            "obj-3",
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
            "obj-12",
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
            "obj-14",
            0
          ],
          "destination": [
            "obj-15",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-15",
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
            "obj-17",
            0
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
            "obj-18",
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
            "obj-20",
            0
          ],
          "destination": [
            "obj-21",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-21",
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
            "obj-23",
            0
          ],
          "destination": [
            "obj-24",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-24",
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
            "obj-26",
            0
          ],
          "destination": [
            "obj-27",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-27",
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
            "obj-29",
            0
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
            "obj-29",
            1
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-3",
            2
          ],
          "destination": [
            "obj-29",
            2
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-3",
            3
          ],
          "destination": [
            "obj-29",
            3
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-3",
            4
          ],
          "destination": [
            "obj-29",
            4
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-3",
            5
          ],
          "destination": [
            "obj-29",
            5
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-3",
            6
          ],
          "destination": [
            "obj-29",
            6
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-3",
            7
          ],
          "destination": [
            "obj-29",
            7
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-29",
            0
          ],
          "destination": [
            "obj-30",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-30",
            0
          ],
          "destination": [
            "obj-31",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-32",
            0
          ],
          "destination": [
            "obj-33",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-33",
            0
          ],
          "destination": [
            "obj-31",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-31",
            0
          ],
          "destination": [
            "obj-34",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-34",
            0
          ],
          "destination": [
            "obj-35",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-34",
            1
          ],
          "destination": [
            "obj-35",
            1
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-34",
            2
          ],
          "destination": [
            "obj-35",
            2
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-35",
            0
          ],
          "destination": [
            "obj-36",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-35",
            1
          ],
          "destination": [
            "obj-36",
            1
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-31",
            1
          ],
          "destination": [
            "obj-37",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-30",
            0
          ],
          "destination": [
            "obj-38",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-39",
            0
          ],
          "destination": [
            "obj-40",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-40",
            0
          ],
          "destination": [
            "obj-38",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-38",
            0
          ],
          "destination": [
            "obj-41",
            0
          ]
        }
      }
    ]
  }
}