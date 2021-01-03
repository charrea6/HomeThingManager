import os
import re

re_1mb_image = re.compile(r'homething\.app[12]__(.*)\.ota')
re_image = re.compile(r'homething__(.*)\.ota')


class Updater:
    def __init__(self, updates_dir, mqtt_handler):
        self.updates_dir = updates_dir
        self.mqtt_handler = mqtt_handler

    def get_versions(self, device):
        flash_type = ''
        for entry in device.sw.capabilities.split(','):
            if entry.startswith('flash'):
                flash_type = entry
                break
        versions = set()
        if flash_type == 'flash1MB':
            regex = re_1mb_image
        else:
            regex = re_image

        for filename in os.listdir(self.updates_dir):
            m = regex.match(filename)
            if m:
                versions.add(m.group(1))
        versions = list(versions)
        versions.sort()
        return versions

    async def update(self, device, version):
        topic = f'homething/{device.uuid}/sw/update'
        await self.mqtt_handler.send_message(topic, version)
