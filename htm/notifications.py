from collections import defaultdict


class NotificationsManager:
    def __init__(self):
        self.device_listeners = defaultdict(list)
        self.all_listeners = []

    def add_device_listener(self, device, listener):
        self.device_listeners[device].append(listener)

    def remove_device_listener(self, device, listener):
        self.device_listeners[device].remove(listener)

    def add_listener(self, listener):
        self.all_listeners.append(listener)

    def remove_listener(self, listener):
        self.all_listeners.remove(listener)

    def send_notification(self, device, event, data):
        for listener in self.device_listeners[device] + self.all_listeners:
            listener(device, event, data)


manager = NotificationsManager()
