from __future__ import annotations
from typing import List
from dataclasses import dataclass
from enum import IntEnum


class MessageType(IntEnum):
    BOOL = 0
    INT = 1
    FLOAT = 2
    STRING = 3
    BINARY = 4
    HUNDREDTHS = 5
    CELSIUS = 6
    PERCENT_RH = 7
    KPA = 8


@dataclass(frozen=True)
class TopicInfo:
    path: str
    message_type: int

    def get_path(self, device_uuid: str, entry: TopicEntry):
        if self.path:
            return f"homething/{device_uuid}/{entry.path}/{self.path}"
        return f"homething/{device_uuid}/{entry.path}"

    @staticmethod
    def list_from_dict(topics_dict) -> List[TopicInfo]:
        return [TopicInfo(pub_path, message_type) for pub_path, message_type in topics_dict.items()]


@dataclass(frozen=True)
class TopicEntry:
    path: str
    pubs: List[TopicInfo]
    subs: List[TopicInfo]

    def __hash__(self):
        return hash((self.path,) + tuple(self.pubs) + tuple(self.subs))
