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
          "text": "Pulse Field — Stage 0: FIELD STATE (source of truth)",
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
          "text": "udpreceive 7400",
          "numinlets": 0,
          "numoutlets": 1,
          "patching_rect": [
            20,
            44,
            150,
            22
          ],
          "outlettype": [
            ""
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
            90,
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
          "maxclass": "toggle",
          "numinlets": 1,
          "numoutlets": 1,
          "outlettype": [
            "int"
          ],
          "patching_rect": [
            200,
            44,
            24,
            24
          ],
          "id": "obj-4"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend freeze",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            200,
            74,
            100,
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
          "text": "freeze",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            230,
            46,
            60,
            20
          ],
          "id": "obj-6"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "route pressure stability density discomfort silence novelty urgency momentum",
          "numinlets": 1,
          "numoutlets": 9,
          "patching_rect": [
            20,
            150,
            360,
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
            ""
          ],
          "id": "obj-7"
        }
      },
      {
        "box": {
          "maxclass": "live.dial",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "pressure",
          "patching_rect": [
            20,
            190,
            48,
            48
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "pressure",
              "parameter_shortname": "pressure",
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
          "text": "prepend set",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            20,
            250,
            70,
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
          "maxclass": "newobj",
          "text": "prepend pressure",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            20,
            310,
            90,
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
          "maxclass": "newobj",
          "text": "prepend param",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            20,
            340,
            90,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-11"
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
            178,
            60,
            20
          ],
          "id": "obj-12"
        }
      },
      {
        "box": {
          "maxclass": "live.dial",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "stability",
          "patching_rect": [
            104,
            190,
            48,
            48
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "stability",
              "parameter_shortname": "stability",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-13"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend set",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            104,
            250,
            70,
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
          "maxclass": "newobj",
          "text": "prepend stability",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            104,
            310,
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
          "maxclass": "newobj",
          "text": "prepend param",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            104,
            340,
            90,
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
          "text": "stabil",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            104,
            178,
            60,
            20
          ],
          "id": "obj-17"
        }
      },
      {
        "box": {
          "maxclass": "live.dial",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "density",
          "patching_rect": [
            188,
            190,
            48,
            48
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "density",
              "parameter_shortname": "density",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-18"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend set",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            188,
            250,
            70,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-19"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend density",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            188,
            310,
            90,
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
          "maxclass": "newobj",
          "text": "prepend param",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            188,
            340,
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
          "text": "densit",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            188,
            178,
            60,
            20
          ],
          "id": "obj-22"
        }
      },
      {
        "box": {
          "maxclass": "live.dial",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "discomfort",
          "patching_rect": [
            272,
            190,
            48,
            48
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "discomfort",
              "parameter_shortname": "discomfort",
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
          "text": "prepend set",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            272,
            250,
            70,
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
          "maxclass": "newobj",
          "text": "prepend discomfort",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            272,
            310,
            90,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-25"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend param",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            272,
            340,
            90,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-26"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "discom",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            272,
            178,
            60,
            20
          ],
          "id": "obj-27"
        }
      },
      {
        "box": {
          "maxclass": "live.dial",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "silence",
          "patching_rect": [
            356,
            190,
            48,
            48
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "silence",
              "parameter_shortname": "silence",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-28"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend set",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            356,
            250,
            70,
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
          "text": "prepend silence",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            356,
            310,
            90,
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
          "text": "prepend param",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            356,
            340,
            90,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-31"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "silenc",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            356,
            178,
            60,
            20
          ],
          "id": "obj-32"
        }
      },
      {
        "box": {
          "maxclass": "live.dial",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "novelty",
          "patching_rect": [
            440,
            190,
            48,
            48
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "novelty",
              "parameter_shortname": "novelty",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-33"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend set",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            440,
            250,
            70,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-34"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend novelty",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            440,
            310,
            90,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-35"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend param",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            440,
            340,
            90,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-36"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "novelt",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            440,
            178,
            60,
            20
          ],
          "id": "obj-37"
        }
      },
      {
        "box": {
          "maxclass": "live.dial",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "urgency",
          "patching_rect": [
            524,
            190,
            48,
            48
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "urgency",
              "parameter_shortname": "urgency",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-38"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend set",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            524,
            250,
            70,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-39"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend urgency",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            524,
            310,
            90,
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
          "maxclass": "newobj",
          "text": "prepend param",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            524,
            340,
            90,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-41"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "urgenc",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            524,
            178,
            60,
            20
          ],
          "id": "obj-42"
        }
      },
      {
        "box": {
          "maxclass": "live.dial",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "varname": "momentum",
          "patching_rect": [
            608,
            190,
            48,
            48
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_longname": "momentum",
              "parameter_shortname": "momentum",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 1
            }
          },
          "id": "obj-43"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend set",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            608,
            250,
            70,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-44"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend momentum",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            608,
            310,
            90,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-45"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "prepend param",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            608,
            340,
            90,
            22
          ],
          "outlettype": [
            ""
          ],
          "id": "obj-46"
        }
      },
      {
        "box": {
          "maxclass": "comment",
          "text": "moment",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            608,
            178,
            60,
            20
          ],
          "id": "obj-47"
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
            "obj-3",
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
            9
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
            "obj-8",
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
            "obj-10",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-10",
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
            "obj-3",
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
            "obj-14",
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
            "obj-13",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-13",
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
            "obj-16",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-16",
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
            "obj-7",
            2
          ],
          "destination": [
            "obj-19",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-19",
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
            "obj-20",
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
            "obj-7",
            3
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
            "obj-23",
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
            "obj-25",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-25",
            0
          ],
          "destination": [
            "obj-26",
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
            "obj-3",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-7",
            4
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
            "obj-29",
            0
          ],
          "destination": [
            "obj-28",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-28",
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
            "obj-31",
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
            "obj-7",
            5
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
            "obj-35",
            0
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
            "obj-36",
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
            "obj-7",
            6
          ],
          "destination": [
            "obj-39",
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
            "obj-41",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-41",
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
            "obj-7",
            7
          ],
          "destination": [
            "obj-44",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-44",
            0
          ],
          "destination": [
            "obj-43",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-43",
            0
          ],
          "destination": [
            "obj-45",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-45",
            0
          ],
          "destination": [
            "obj-46",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-46",
            0
          ],
          "destination": [
            "obj-3",
            0
          ]
        }
      }
    ]
  }
}