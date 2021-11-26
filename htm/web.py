import os
import datetime
from tornado.web import Application, RequestHandler
from tornado.websocket import WebSocketHandler
import humanize
from parsimonious.exceptions import IncompleteParseError
from cbor2 import dumps
from homething.parse import *
from htm import notifications
from htm import db
from datatables import ColumnDT, DataTables
import json
import pytz


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return str(o)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, o)


class MainPageHandler(RequestHandler):
    def initialize(self, devices):
        self.devices = devices

    def get(self):
        self.render("index.html", devices=self.devices.get_devices())


class DevicePageHandler(RequestHandler):
    def initialize(self, devices):
        self.devices = devices

    def get(self, device_id):
        device = self.devices.get_device(device_id)
        if device is None:
            self.send_error(404)
            return

        self.render("device.html", device=device)

    async def delete(self, device_id):
        device = self.devices.get_device(device_id)
        if device is None:
            self.send_error(404)
            return

        await device.delete()
        self.set_status(200, "deleted")


class DeviceProfilePageHandler(RequestHandler):
    def initialize(self, devices):
        self.devices = devices

    def get(self, device_id):
        device = self.devices.get_device(device_id)
        if device is None:
            self.send_error(404)
            return
        self.render("profile.html", device=device, profile=device.profile, error=None)

    async def post(self, device_id):
        device = self.devices.get_device(device_id)
        if device is None:
            self.send_error(404)
            return

        source = ProfileSource()
        source.filename = ""
        source.text = self.get_argument("profile")
        error_message = ''
        try:
            source.parse()
            profile = source.process()
            await device.set_profile(dumps(profile))
            self.redirect(f'/device/{device.uuid}/')
            return
        except IncompleteParseError as e:
            error_message = source.message_for_location(e.pos, 'error', 'Failed to parse')

        except ProfileEntryError as e:
            error_message = source.message_for_location(e.location, 'error', e.message)
        await self.render("profile.html", device=device, profile=source.text, error=error_message)


class DeviceUpdateHandler(RequestHandler):
    def initialize(self, devices, updates):
        self.devices = devices
        self.updates = updates

    def get(self, device_id):
        device = self.devices.get_device(device_id)
        if device is None:
            self.send_error(404)
            return
        versions = self.updates.get_versions(device)
        self.render("update.html", device=device, versions=versions, error=None)

    async def post(self, device_id):
        device = self.devices.get_device(device_id)
        if device is None:
            self.send_error(404)
            return
        await device.update(self.get_body_argument('version'))
        self.redirect(f'/device/{device.uuid}/')


class DeviceRestartHandler(RequestHandler):
    def initialize(self, devices):
        self.devices = devices

    async def post(self, device_id):
        device = self.devices.get_device(device_id)
        if device is None:
            self.send_error(404)
            return
        await device.reboot()
        self.redirect(f'/device/{device.uuid}/')


class DeviceEventsDatatableHandler(RequestHandler):
    def initialize(self, devices) -> None:
        self.devices = devices

    def get(self, device_id):
        device = self.devices.get_device(device_id)
        if device is None:
            self.send_error(404)
            return

        query = db.get_events_query(device_id)
        columns = [
            ColumnDT(db.Event.id, mData='id'),
            ColumnDT(db.Event.datetime, mData='datetime'),
            ColumnDT(db.Event.event, mData='event'),
            ColumnDT(db.Event.uptime, mData='uptime')
        ]
        args = {k: v[0].decode() for k, v in self.request.arguments.items()}
        row_table = DataTables(args, query, columns)
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        self.write(JSONEncoder().encode(row_table.output_result()))
        self.flush()


class DevicesJsonHandler(RequestHandler):
    def initialize(self, devices) -> None:
        self.devices = devices

    def get(self):
        device_list = {"devices": [
            {"id": device.uuid, "uptime": device.last_uptime, "version": device.info.get('version', ''),
             "online": device.online, "description": device.info.get("description", "")}
            for device in self.devices.get_devices()]}

        self.write(device_list)
        self.flush()


class DeviceMemoryStatsHandler(RequestHandler):
    def initialize(self, devices) -> None:
        self.devices = devices

    def get(self, device_id):
        device = self.devices.get_device(device_id)
        if device is None:
            self.send_error(404)
            return

        free = []
        min_free = []
        times = []
        result = {"free": free, "times": times, "min_free": min_free}
        to_time = datetime.datetime.now(pytz.utc)
        from_time = to_time - datetime.timedelta(days=1)
        for log in db.get_memory_logs(device_id, from_time, to_time):
            times.append(log.datetime)
            min_free.append(log.min_free)
            free.append(log.free)
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        self.write(JSONEncoder().encode(result))
        self.flush()


class DeviceUpdatesWebSocketHandler(WebSocketHandler):
    def initialize(self, devices) -> None:
        self.devices = devices
        self.device = None

    def open(self, device_id):
        self.device = self.devices.get_device(device_id)
        if self.device is None:
            self.send_error(404)
            return

        # Register for notifications
        notifications.manager.add_device_listener(self.device, self.device_listener)

    def device_listener(self, device, event, data):
        self.write_message(JSONEncoder().encode({"event": event, "data": data}))

    def on_message(self, message):
        print(f"Message received: {message}")

    def on_close(self):
        # Cancel notifications
        notifications.manager.remove_device_listener(self.device, self.device_listener)


def get_server(devices, updates):

    return Application([(r'/', MainPageHandler, dict(devices=devices)),
                        (r'/devices', DevicesJsonHandler, dict(devices=devices)),
                        (r'/device/([^/]+)/', DevicePageHandler, dict(devices=devices)),
                        (r'/device/([^/]+)/profile', DeviceProfilePageHandler, dict(devices=devices)),
                        (r'/device/([^/]+)/update', DeviceUpdateHandler, dict(devices=devices, updates=updates)),
                        (r'/device/([^/]+)/restart', DeviceRestartHandler, dict(devices=devices)),
                        (r'/device/([^/]+)/events', DeviceEventsDatatableHandler, dict(devices=devices)),
                        (r'/device/([^/]+)/memorystats', DeviceMemoryStatsHandler, dict(devices=devices)),
                        (r'/device/([^/]+)/ws', DeviceUpdatesWebSocketHandler, dict(devices=devices))
                        ],
                       template_path=os.path.join(os.path.dirname(__file__), 'templates'),
                       static_path=os.path.join(os.path.dirname(__file__), 'static'),
                       debug=True)
