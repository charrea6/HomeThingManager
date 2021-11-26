import os
import os.path
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

        if flash_type == 'flash1MB':
            regex = re_1mb_image
        else:
            regex = re_image

        versions = list()
        for filename in os.listdir(self.updates_dir):
            m = regex.match(filename)
            if m:
                mtime = os.path.getmtime(os.path.join(self.updates_dir, filename))
                versions.append((m.group(1), mtime))
        versions.sort(key=lambda x: x[1], reverse=True)
        return [v for v, _ in versions]
