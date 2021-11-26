import os
import re

re_1mb_image = re.compile(r'homething\.app[12]__(.*)\.ota')
re_image = re.compile(r'homething__(.*)\.ota')


class UpdateManager:
    def __init__(self, updates_dir):
        self.updates_dir = updates_dir

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
