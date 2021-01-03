import os
import datetime
from tornado.web import Application, RequestHandler
import plotly.graph_objects as go
import plotly.io

from parsimonious.exceptions import IncompleteParseError
from cbor2 import dumps
from homething.parse import *



class MainPageHandler(RequestHandler):
    def initialize(self, db):
        self.db = db

    def get(self):
        self.render("index.html", devices=self.db.get_devices())


class DevicePageHandler(RequestHandler):
    def initialize(self, db):
        self.db = db

    def get(self, device_id):
        device = self.db.get_device(device_id)
        if device is None:
            self.send_error(404)
            return
        if device.memory_free_log:
            fig = go.Figure()

            times = [e.event_time for e in device.memory_free_log]
            times.append(datetime.datetime.now())

            measurements = [e.bytes_free for e in device.memory_free_log]
            measurements.append(device.memory_free_log[-1].bytes_free)

            fig.add_trace(go.Scatter(x=times, y=measurements, name="Free Memory"))
            if device.min_memory_log:
                times = [e.event_time for e in device.min_memory_log]
                times.append(datetime.datetime.now())

                measurements = [e.bytes_free for e in device.min_memory_log]
                measurements.append(device.min_memory_log[-1].bytes_free)
                fig.add_trace(go.Scatter(x=times, y=measurements, name="Minimum Free Memory"))

            memory_free_div = plotly.io.to_html(fig, include_plotlyjs='cdn', include_mathjax='cdn', full_html=False)
        else:
            memory_free_div = '<i>No memory statistics</i>'

        self.render("device.html", device=device, memory_free_div=memory_free_div)


class DeviceProfilePageHandler(RequestHandler):
    def initialize(self, db, mqtt_handler):
        self.db = db
        self.mqtt_handler = mqtt_handler

    def get(self, device_id):
        device = self.db.get_device(device_id)
        if device is None:
            self.send_error(404)
            return
        self.render("profile.html", device=device, profile=device.profile, error=None)

    async def post(self, device_id):
        device = self.db.get_device(device_id)
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
            profile_str = dumps(profile)
            topic = f'homething/{device.uuid}/device/ctrl'
            await self.mqtt_handler.send_message(topic, b'setprofile\0' + profile_str)
            self.redirect(f'/device/{device.uuid}/')
            return
        except IncompleteParseError as e:
            error_message = source.message_for_location(e.pos, 'error', 'Failed to parse')

        except ProfileEntryError as e:
            error_message = source.message_for_location(e.location, 'error', e.message)
        await self.render("profile.html", device=device, profile=source.text, error=error_message)


def get_server(db, mqtt_handler):
    return Application([(r'/', MainPageHandler, dict(db=db)),
                        (r'/device/([^/]+)/', DevicePageHandler, dict(db=db)),
                        (r'/device/([^/]+)/profile', DeviceProfilePageHandler, dict(db=db, mqtt_handler=mqtt_handler))
                        ],
                       template_path=os.path.join(os.path.dirname(__file__), 'templates'),
                       debug=True)
