import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(levelname)s : %(message)s")

import tornado.ioloop
import argparse
from htm.db import Database
import htm.mqtt as mqtt
import htm.web as web

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Web based HomeThing Manager")
    parser.add_argument("--updates_dir", type=str, help="Location of firmware update files.")
    parser.add_argument("--ip", type=str, help="IP address to bind to, by default this is all IPs", default="0.0.0.0")
    parser.add_argument("--port", type=int, help="Port to make the web server available on.", default=8888)
    parser.add_argument("--mqtt", type=str, help="URL for the MQTT server to connect to.", default="mqtt://localhost")
    args = parser.parse_args()

    db = Database()

    mqtt_handler = mqtt.get_handler(args.mqtt, db)
    mqtt_handler.connect()

    web_server = web.get_server(db, mqtt_handler)
    web_server.listen(args.port, args.ip)

    tornado.ioloop.IOLoop.current().start()
