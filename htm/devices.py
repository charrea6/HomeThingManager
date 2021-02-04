from collections import defaultdict
import time
import datetime
import humanize
import cbor2
from homething.decode import decode as decode_profile
from .db import add_memory_log, add_event
import pytz


class AttributeAccessDictionary(dict):
    def __getattr__(self, item):
        if item in self.keys():
            return self.get(item)
        raise AttributeError(f"No such item: {item}")


class TopicInfo:
    def __init__(self, entry, path, message_type):
        self.entry = entry
        self.path = path
        self.message_type = message_type


class TopicEntry:
    def __init__(self, path, pubs, subs):
        self.path = path
        self.pubs = [TopicInfo(self, pub_path, message_type) for pub_path, message_type in pubs.items()]
        self.subs = [TopicInfo(self, sub_path, message_type) for sub_path, message_type in subs.items()]


class Device:
    ALIVE_UPTIME_THRESHOLD = 10
    MAX_EVENTS = 1000

    def __init__(self, uuid):
        self.uuid = uuid
        self.properties = defaultdict(AttributeAccessDictionary)
        self.online = False
        self.last_uptime_update = 0
        self.last_uptime = 0
        self.profile = ''
        self.entries = []
        self.current_free = None
        self.current_min_free = None

    def update_property(self, prop_path, value):
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
        descriptions = topics[0]
        entries = topics[1]
        for name, description_id in entries.items():
            pubs, subs = descriptions[description_id]
            self.entries.append(TopicEntry(name, pubs, subs))

    def add_event(self, event, uptime):
        add_event(self.uuid, event, uptime)


class Devices:
    def __init__(self):
        self.devices = {}

    def update_device(self, uuid, prop_path, value):
        device = self.devices.get(uuid)
        if device is None:
            device = Device(uuid)
            self.devices[uuid] = device
        device.update_property(prop_path, value)

    def get_device(self, uuid):
        return self.devices.get(uuid)

    def get_devices(self):
        return self.devices.values()

    def check_devices_online(self):
        for device in self.devices.values():
            device.check_online()


