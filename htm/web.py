import os
from tornado.web import Application, RequestHandler
import plotly.graph_objects as go
import plotly.io


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
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[e.event_time for e in device.memory_free_log],
                                 y=[e.bytes_free for e in device.memory_free_log],
                                 name="Free Memory"))
        fig.add_trace(go.Scatter(x=[e.event_time for e in device.min_memory_log],
                                 y=[e.bytes_free for e in device.min_memory_log],
                                 name="Minimum Free Memory"))

        memory_free_div = plotly.io.to_html(fig, include_plotlyjs='cdn', include_mathjax='cdn', full_html=False)
        self.render("device.html", device=device, memory_free_div=memory_free_div)


def get_server(db):
    return Application([(r'/', MainPageHandler, dict(db=db)),
                        (r'/device/([^/]+)/', DevicePageHandler, dict(db=db))
                        ],
                       template_path=os.path.join(os.path.dirname(__file__), 'templates'),
                       debug=True)
