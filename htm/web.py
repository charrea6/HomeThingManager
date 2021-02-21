import os
import datetime
from tornado.web import Application, RequestHandler
import plotly.graph_objects as go
import plotly.io
import humanize
from parsimonious.exceptions import IncompleteParseError
from cbor2 import dumps
from homething.parse import *
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
    def initialize(self, devices, mqtt_handler):
        self.devices = devices
        self.mqtt_handler = mqtt_handler

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

        await device.delete(self.mqtt_handler)
        self.set_status(200, "deleted")


class DeviceProfilePageHandler(RequestHandler):
    def initialize(self, devices, mqtt_handler):
        self.devices = devices
        self.mqtt_handler = mqtt_handler

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
            await device.set_profile(self.mqtt_handler, dumps(profile))
            self.redirect(f'/device/{device.uuid}/')
            return
        except IncompleteParseError as e:
            error_message = source.message_for_location(e.pos, 'error', 'Failed to parse')

        except ProfileEntryError as e:
            error_message = source.message_for_location(e.location, 'error', e.message)
        await self.render("profile.html", device=device, profile=source.text, error=error_message)


class DeviceUpdateHandler(RequestHandler):
    def initialize(self, devices, updater):
        self.devices = devices
        self.updater = updater

    def get(self, device_id):
        device = self.devices.get_device(device_id)
        if device is None:
            self.send_error(404)
            return
        versions = self.updater.get_versions(device)
        self.render("update.html", device=device, versions=versions, error=None)

    async def post(self, device_id):
        device = self.devices.get_device(device_id)
        if device is None:
            self.send_error(404)
            return
        await self.updater.update(device, self.get_body_argument('version'))
        self.redirect(f'/device/{device.uuid}/')


class DeviceRestartHandler(RequestHandler):
    def initialize(self, devices, mqtt_handler):
        self.devices = devices
        self.mqtt_handler = mqtt_handler

    async def post(self, device_id):
        device = self.devices.get_device(device_id)
        if device is None:
            self.send_error(404)
            return
        await device.reboot(self.mqtt_handler)
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
            {"id": device.uuid, "uptime": device.last_uptime, "version": device.sw.version, "online": device.online}
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


def get_server(devices, mqtt_handler, updater):

    return Application([(r'/', MainPageHandler, dict(devices=devices)),
                        (r'/devices', DevicesJsonHandler, dict(devices=devices)),
                        (r'/device/([^/]+)/', DevicePageHandler, dict(devices=devices, mqtt_handler=mqtt_handler)),
                        (r'/device/([^/]+)/profile', DeviceProfilePageHandler, dict(devices=devices, mqtt_handler=mqtt_handler)),
                        (r'/device/([^/]+)/update', DeviceUpdateHandler, dict(devices=devices, updater=updater)),
                        (r'/device/([^/]+)/restart', DeviceRestartHandler, dict(devices=devices, mqtt_handler=mqtt_handler)),
                        (r'/device/([^/]+)/events', DeviceEventsDatatableHandler, dict(devices=devices)),
                        (r'/device/([^/]+)/memorystats', DeviceMemoryStatsHandler, dict(devices=devices))
                        ],
                       template_path=os.path.join(os.path.dirname(__file__), 'templates'),
                       static_path=os.path.join(os.path.dirname(__file__), 'static'),
                       debug=True)
