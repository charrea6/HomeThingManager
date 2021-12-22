from collections import defaultdict
import yaml
import os.path

from .constants import *
from .errors import *


switch_types = {}
relay_types = {}


def decode_switch(entry):
    pin = entry[1]
    switch_type = entry[2]
    return f'{switch_types[switch_type]}({pin})', None


def decode_relay(entry):
    pin = entry[1]
    level = entry[2]
    relay_type = entry[3]
    if relay_type == DeviceProfile_RelayController_None:
        return f'relay({pin}, {level})', None
    controller_id = entry[4]
    return f'{relay_types[relay_type]}({pin}, {level}, id{controller_id})', controller_id


def decode_led_strip_spi(entry):
    count = entry[1]
    return f'led_strip_spi({count})', None


def decode_draytonscr(entry):
    pin = entry[1]
    on_sequence = entry[2]
    off_sequence = entry[3]
    controller_id = entry[4]
    return f'draytonscr({pin}, "{on_sequence}", "{off_sequence}", id{controller_id})', controller_id


class DecodeFactory:
    def __init__(self, name, details):
        self.name = name


class GPIOPinComponentFactory(DecodeFactory):
    def __call__(self, entry):
        return f"{self.name}({entry[1]})", None


class I2CDeviceFactory(DecodeFactory):
    def __init__(self, name, details):
        super().__init__(name, details)
        self.addr = details['addr']

    def __call__(self, entry):
        sda = entry[1]
        scl = entry[2]
        addr = entry[3]
        if addr == self.addr:
            return f'{self.name}({sda}, {scl})', None
        return f'{self.name}({sda}, {scl}, {addr})', None


decoders = {
    DeviceProfile_EntryType_GPIOSwitch: decode_switch,
    DeviceProfile_EntryType_Relay: decode_relay,
    DeviceProfile_EntryType_LEDStripSPI: decode_led_strip_spi,
    DeviceProfile_EntryType_DraytonSCR: decode_draytonscr
}

with open(os.path.join(os.path.dirname(__file__), "components.yaml")) as fp:
    for name, details in yaml.safe_load(fp).items():
        component_type = details['type']

        if component_type == 'gpio_pin':
            decoders[details['id']] = GPIOPinComponentFactory(name, details)

        elif component_type == 'i2c':
            decoders[details['id']] = I2CDeviceFactory(name, details)

        elif component_type == 'gpio_switch':
            switch_types[details['switchType']] = name

        elif component_type == 'gpio_relay':
            relay_types[details['relayType']] = name

        elif component_type in ('led_strip_spi', 'draytonscr'):
            pass

        else:
            raise RuntimeError(f"Unknown component type {component_type} for {name}")


def decode(profile):
    version = profile[0]
    if version != 1:
        raise UnsupportedProfileVersionError()
    entries = []
    referenced_entries = defaultdict(list)
    for entry in profile[1:]:
        desc, used = decoders[entry[0]](entry)
        if used is not None:
            referenced_entries[used].append(len(entries))
        entries.append(desc)
    source = ''
    for i, entry in enumerate(entries):
        if i in referenced_entries:
            used_by = referenced_entries[i]
            if len(used_by) == 1 and used_by[0] == i + 1:
                entries[i + 1] = entries[i + 1].replace(f'id{i}', entry)
            else:
                source += f'id{i} = {entry}\n'
        else:
            source += entry + '\n'

    return source
