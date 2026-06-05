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
      560,
      460
    ],
    "openinpresentation": 0,
    "boxes": [
      {
        "box": {
          "maxclass": "comment",
          "text": "Pulse Field — Stage 3: MONITOR",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            10,
            300,
            20
          ],
          "id": "obj-1"
        }
      },
      {
        "box": {
          "maxclass": "newobj",
          "text": "js monitor.js",
          "numinlets": 1,
          "numoutlets": 3,
          "patching_rect": [
            20,
            44,
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
          "id": "obj-2"
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
            20,
            90,
            520,
            320
          ],
          "saved_object_attributes": {
            "filename": "monitor-ui.js",
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
            170,
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
          "text": "metro 16",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            200,
            44,
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
          "text": "on/off -> 16ms repaint; feed field via observe/inlet",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20,
            414,
            520,
            20
          ],
          "id": "obj-6"
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
            "obj-2",
            0
          ]
        }
      }
    ]
  }
}