from __future__ import annotations
from collections import defaultdict
import json
import time
import datetime
import humanize
import cbor2
from homething.decode import decode as decode_profile
from .db import add_memory_log, add_event
from .deviceinfo import TopicInfo, TopicEntry
from .homeassistant import get_home_assistant_configs
import asyncio


class AttributeAccessDictionary(dict):
    def __getattr__(self, item):
        if item in self.keys():
            return self.get(item)
        raise AttributeError(f"No such item: {item}")


class Device:
    ALIVE_UPTIME_THRESHOLD = 10
    MAX_EVENTS = 1000

    def __init__(self, devices, uuid):
        self.devices = devices
        self.uuid = uuid
        self.properties = defaultdict(AttributeAccessDictionary)
        self.online = False
        self.last_uptime_update = 0
        self.last_uptime = 0
        self.profile = ''
        self.entries = []
        self.current_free = None
        self.current_min_free = None
        self.retained_topics = set()

    def update_property(self, prop_path, value, retain):
        if retain:
            self.retained_topics.add('/'.join(prop_path))
            if value == b'':
                return

        if prop_path[0] == 'device':
            if prop_path[1] == 'uptime':
                new_uptime = int(value.decode())
                if new_uptime <= self.last_uptime:
                    self.add_event("reboot", new_uptime)

                if not self.online:
                    self.add_event("online", new_uptime)
                self.online = True

                self.last_uptime = new_uptime
                self.last_uptime_update = time.time()

            elif prop_path[1] == 'memFree':
                mem_free = int(value.decode())

                self.current_free = mem_free
                if self.current_min_free is not None:
                    if mem_free < self.current_min_free:
                        self.current_min_free = mem_free
                    add_memory_log(self.uuid, mem_free, self.current_min_free)

            elif prop_path[1] == 'memLow':
                mem_free = int(value.decode())
                self.current_min_free = mem_free

                if self.current_free is not None:
                    add_memory_log(self.uuid, self.current_free, self.current_min_free)

            elif prop_path[1] == 'profile':
                profile_data = cbor2.loads(value)
                self.profile = decode_profile(profile_data)

            elif prop_path[1] == 'topics':
                topics_data = cbor2.loads(value)
                self.process_topics(topics_data)

        if len(prop_path) == 1:
            self.properties[prop_path[0]]['default'] = value.decode()
        else:
            try:
                self.properties[prop_path[0]][prop_path[1]] = value.decode()
            except UnicodeDecodeError:
                try:
                    self.properties[prop_path[0]][prop_path[1]] = cbor2.loads(value)
                except (cbor2.CBORDecodeError, UnicodeDecodeError):
                    self.properties[prop_path[0]][prop_path[1]] = value

    def is_alive(self):
        now = time.time()
        return self.last_uptime_update + self.ALIVE_UPTIME_THRESHOLD > now

    def check_online(self):
        now = time.time()
        if self.online and now - self.last_uptime_update > self.ALIVE_UPTIME_THRESHOLD:
            self.online = False
            self.add_event("offline", self.last_uptime)

    def __getattr__(self, item):
        if item in self.properties:
            return self.properties[item]
        raise AttributeError(f"No such property: {item}")

    @property
    def uptime_str(self):
        return humanize.precisedelta(datetime.timedelta(seconds=self.last_uptime))

    def process_topics(self, topics):
        self.entries = []

        descriptions = {}
        for description_id, (raw_pubs, raw_subs) in topics[0].items():
            descriptions[description_id] = (TopicInfo.list_from_dict(raw_pubs), TopicInfo.list_from_dict(raw_subs))

        for name, description_id in topics[1].items():
            pubs, subs = descriptions[description_id]
            entry = TopicEntry(name, pubs, subs)
            self.entries.append(entry)

    def add_event(self, event, uptime):
        add_event(self.uuid, event, uptime)

    async def set_profile(self, profile):
        topic = f'homething/{self.uuid}/device/ctrl'
        await self.devices.mqtt.send_message(topic, b'setprofile\0' + profile)

    async def reboot(self):
        topic = f'homething/{self.uuid}/device/ctrl'
        await self.devices.mqtt.send_message(topic, b'restart')

    async def delete(self):
        for topic_path in self.retained_topics:
            if topic_path == 'device/uptime':
                continue

            topic = f'homething/{self.uuid}/{topic_path}'
            await self.devices.mqtt.send_message(topic, b'', retain=True)

        topic = f'homething/{self.uuid}/device/uptime'
        await self.devices.mqtt.send_message(topic, b'', retain=True)


class Devices:
    def __init__(self):
        self.devices = {}
        self.mqtt = None

    def update_device(self, uuid, prop_path, value, retain):
        device = self.devices.get(uuid)
        if device is None:
            if prop_path == ['device', 'uptime'] and value == b'':
                return
            device = Device(self, uuid)
            self.devices[uuid] = device

        if prop_path == ['device', 'uptime'] and value == b'':
            del self.devices[uuid]
        device.update_property(prop_path, value, retain)

    def get_device(self, uuid):
        return self.devices.get(uuid)

    def get_devices(self):
        return self.devices.values()

    def check_devices_online(self):
        for device in self.devices.values():
            device.check_online()


