import asyncio
import logging
from urllib.parse import urlparse

import aio_mqtt
import asyncio_mqtt


logger = logging.getLogger(__name__)


class MQTTHandler:
    def __init__(self, url: str, db):
        self.url_details = urlparse(url)
        if self.url_details.scheme not in ('mqtt', 'mqtts'):
            raise RuntimeError('Unsupported URL for MQTT "%s"' % url)
        self.db = db
        db.mqtt = self
        self.task = None
        self._loop = asyncio.get_event_loop()
        self._reconnection_interval = 10

    def connect(self):
        logger.info("Creating task...")
        self.task = self._loop.create_task(self.process())

    def _get_connection_details(self):
        kwargs = {}
        host = self.url_details.hostname
        if self.url_details.scheme == 'mqtts':
            kwargs['ssl'] = True
        if self.url_details.port is not None:
            kwargs['port'] = self.url_details.port
        if self.url_details.username is not None:
            kwargs['username'] = self.url_details.username
        if self.url_details.password is not None:
            kwargs['password'] = self.url_details.password
        return host, kwargs

    async def send_message(self, topic, message, retain=False):
        raise NotImplementedError('send_message needs to be implemented by subclass')


class AIOMqttHandler(MQTTHandler):
    def __init__(self, url: str, db):
        super().__init__(url, db)
        self._client = aio_mqtt.Client(loop=self._loop)

    async def process(self):
        while True:
            try:
                host, kwargs = self._get_connection_details()
                await self._client.connect(host, **kwargs)
                logger.info("Connected")

                await self._client.subscribe(('homething/#', aio_mqtt.QOSLevel.QOS_1))
                async for message in self._client.delivered_messages():
                    try:
                        self.process_message(message)
                    except Exception:
                        logger.error("Failed to process message", exc_info=True)

            except asyncio.CancelledError:
                raise

            except aio_mqtt.AccessRefusedError as e:
                logger.error("Access refused", exc_info=e)

            except aio_mqtt.ConnectionLostError as e:
                logger.error("Connection lost. Will retry in %d seconds", self._reconnection_interval, exc_info=e)
                await asyncio.sleep(self._reconnection_interval, loop=self._loop)

            except aio_mqtt.ConnectionCloseForcedError as e:
                logger.error("Connection close forced", exc_info=e)
                return

            except Exception as e:
                logger.error("Unhandled exception during connecting", exc_info=e)
                return

            else:
                logger.info("Disconnected")
                return

    def process_message(self, message):
        topic_elements = message.topic_name.split('/')
        uuid = topic_elements[1]
        self.db.update_device(uuid, topic_elements[2:], message.payload.decode(), message.retain)

    async def send_message(self, topic, message, retain=False):
        await self._client.publish(aio_mqtt.PublishableMessage(topic, message, retain=retain))


class AsyncioMqttHandler(MQTTHandler):
    async def process(self):
        logger.info("Starting...")
        host, kwargs = self._get_connection_details()
        async with asyncio_mqtt.Client(host, **kwargs) as client:
            self.client = client
            logger.info("Connected")
            async with client.filtered_messages("homething/#") as messages:
                logger.info("About to subscribe..")
                await client.subscribe("homething/#")
                logger.info("Subscribed.")
                async for message in messages:
                    try:
                        self.process_message(message)
                    except:
                        logger.error("Processing message failed!", exc_info=True)

    def process_message(self, message):
        topic_elements = message.topic.split('/')
        uuid = topic_elements[1]
        self.db.update_device(uuid, topic_elements[2:], message.payload, message.retain)

    async def send_message(self, topic, message, retain=False):
        await self.client.publish(topic, message, retain=retain)


def get_handler(url, db):
    return AsyncioMqttHandler(url, db)
