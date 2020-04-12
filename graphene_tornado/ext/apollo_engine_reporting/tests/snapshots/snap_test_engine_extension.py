# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots[
    "test_can_send_report_to_engine 1"
] = """{
  "durationNs": "-1",
  "endTime": "2019-09-21T19:37:09.908919Z",
  "http": {
    "method": "GET"
  },
  "root": {
    "child": [
      {
        "endTime": "-1",
        "parentType": "Query",
        "responseName": "author",
        "startTime": "-1",
        "type": "User"
      },
      {
        "endTime": "-1",
        "parentType": "Query",
        "responseName": "aBoolean",
        "startTime": "-1",
        "type": "Boolean"
      },
      {
        "child": [
          {
            "endTime": "-1",
            "parentType": "User",
            "responseName": "name",
            "startTime": "-1",
            "type": "String"
          }
        ],
        "responseName": "author"
      },
      {
        "child": [
          {
            "endTime": "-1",
            "parentType": "User",
            "responseName": "posts",
            "startTime": "-1",
            "type": "[Post]"
          }
        ],
        "responseName": "author"
      },
      {
        "child": [
          {
            "child": [
              {
                "child": [
                  {
                    "endTime": "-1",
                    "parentType": "Post",
                    "responseName": "id",
                    "startTime": "-1",
                    "type": "Int"
                  }
                ],
                "index": 0
              }
            ],
            "responseName": "posts"
          }
        ],
        "responseName": "author"
      },
      {
        "child": [
          {
            "child": [
              {
                "child": [
                  {
                    "endTime": "-1",
                    "parentType": "Post",
                    "responseName": "id",
                    "startTime": "-1",
                    "type": "Int"
                  }
                ],
                "index": 1
              }
            ],
            "responseName": "posts"
          }
        ],
        "responseName": "author"
      }
    ],
    "endTime": "-1",
    "startTime": "-1"
  },
  "startTime": "2019-09-21T19:37:09.908919Z"
}"""
