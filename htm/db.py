from collections import defaultdict
import time
import datetime
import humanize


class AttributeAccessDictionary(dict):
    def __getattr__(self, item):
        if item in self.keys():
            return self.get(item)
        raise AttributeError(f"No such item: {item}")


class RebootEvent:
    def __init__(self, previous_uptime, new_uptime):
        self.event_time = datetime.datetime.now() - datetime.timedelta(seconds=new_uptime)
        self.uptime = previous_uptime


class MemoryEvent:
    def __init__(self, bytes_free, event_time=None):
        if event_time is None:
            self.event_time = datetime.datetime.now()
        else:
            self.event_time = event_time
        self.bytes_free = bytes_free


class Device:
    ALIVE_UPTIME_THRESHOLD = 10
    MAX_EVENTS = 1000

    def __init__(self, uuid):
        self.uuid = uuid
        self.properties = defaultdict(AttributeAccessDictionary)
        self.last_uptime_update = 0
        self.last_uptime = 0
        self.reboots = []
        self.memory_free_log = []
        self.min_memory_log = []

    def update_property(self, prop_path, value):
        if prop_path[0] == 'device':
            if prop_path[1] == 'uptime':
                new_uptime = int(value)
                if new_uptime <= self.last_uptime:
                    self.reboots.append(RebootEvent(self.last_uptime, new_uptime))
                self.last_uptime = new_uptime
                self.last_uptime_update = time.time()
            elif prop_path[1] == 'memFree':
                mem_free = int(value)
                self.memory_free_log.append(MemoryEvent(mem_free))
                if len(self.memory_free_log) > Device.MAX_EVENTS:
                    self.memory_free_log = self.memory_free_log[len(self.memory_free_log) - Device.MAX_EVENTS:]

            elif prop_path[1] == 'memLow':
                mem_free = int(value)
                self.min_memory_log.append(MemoryEvent(mem_free))
                if len(self.min_memory_log) > Device.MAX_EVENTS:
                    self.min_memory_log = self.min_memory_log[len(self.min_memory_log) - Device.MAX_EVENTS:]

        if len(prop_path) == 1:
            self.properties[prop_path[0]]['default'] = value
        else:
            self.properties[prop_path[0]][prop_path[1]] = value

    def is_alive(self):
        now = time.time()
        return self.last_uptime_update + self.ALIVE_UPTIME_THRESHOLD > now

    def __getattr__(self, item):
        if item in self.properties:
            return self.properties[item]
        raise AttributeError(f"No such property: {item}")

    @property
    def uptime_str(self):
        return humanize.precisedelta(datetime.timedelta(seconds=self.last_uptime))


class Database:
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
