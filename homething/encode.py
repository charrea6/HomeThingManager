import yaml
import os.path

from .constants import *
from .errors import *


class Component:
    TYPE_NAME = "Unknown"
    PINS_TABLE = object()

    def __init__(self, pos, args):
        self.pos = pos
        self.args = args
        self.id_table = None

    def process(self, id_table, profile):
        self.id_table = id_table
        self.process_component(profile)

    def check_arg_count(self, required_args):
        if len(self.args) != required_args:
            raise ProfileEntryIncorrectNumberArgumentsError(self.pos, self.TYPE_NAME, len(self.args), required_args)

    def get_pin(self, index):
        pin = self.get_arg(index, (int, ID))
        if isinstance(pin.arg, ID):

            try:
                pins = self.id_table[self.PINS_TABLE]
            except KeyError:
                raise ProfileEntryError(pin.pos, f'Board type not set!')

            try:
                return pins[pin.arg.name]
            except KeyError:
                raise ProfileEntryError(pin.pos, f'Unknown pin name "{pin.arg.name}"')
        else:
            if pin.arg < 0:
                raise ProfileEntryError(pin.pos, "Pin cannot be negative")
        return pin.arg

    def get_id_value(self, arg):
        try:
            return self.id_table[arg.arg.name]
        except KeyError:
            raise ProfileEntryError(arg.pos, f'ID "{arg.arg.name}" not found')

    def get_arg(self, index, types):
        try:
            arg = self.args[index]
            if isinstance(arg.arg, types):
                return arg
            raise ProfileEntryWrongArgumentTypeError(arg, types)
        except IndexError:
            raise ProfileEntryError(self.pos, f"Not enough arguments when looking for argument {index}")


class Switch(Component):
    TYPE_NAME = "switch"

    def __init__(self, type, pos, args):
        super().__init__(pos, args)
        self.type = type

    def process_component(self, profile):
        self.check_arg_count(1)
        entry = [DeviceProfile_EntryType_GPIOSwitch, self.get_pin(0), self.type]
        profile.append(entry)


class BaseRelay(Component):
    TYPE_NAME = "relay"

    def __init__(self, type, pos, args):
        super().__init__(pos, args)
        self.type = type

    def process_component(self, profile):
        self.check_arg_count(2 if self.type == DeviceProfile_RelayController_None else 3)
        entry = [DeviceProfile_EntryType_Relay, self.get_pin(0), self.get_level(), self.type]
        if self.type != DeviceProfile_RelayController_None:
            id = self.get_arg(2, (ID, Component))
            if isinstance(id.arg, ID):
                entry.append(self.get_id_value(id))
            else:
                entry.append(len(profile) - 1)
                id.arg.process(self.id_table, profile)
        profile.append(entry)

    def get_level(self):
        level = self.get_arg(1, int)
        if level.arg not in (0, 1):
            raise ProfileEntryError(level.pos, f'Level must be either 0 or 1 not "{level.arg}"')
        return level.arg


class GPIOPinComponent(Component):
    def __init__(self, name, component_id, pos, args):
        super().__init__(pos, args)
        self.TYPE_NAME = name
        self.component_id = component_id

    def process_component(self, profile):
        self.check_arg_count(1)
        entry = [self.component_id, self.get_pin(0)]
        profile.append(entry)


class I2cDevice(Component):
    def __init__(self, name, component_id, default_addr, pos, args):
        super().__init__(pos, args)
        self.TYPE_NAME = name
        self.default_addr = default_addr
        self.component_id = component_id

    def process_component(self, profile):
        if len(self.args) < 2 or len(self.args) > 3:
            raise ProfileEntryIncorrectNumberArgumentsError(self.pos, self.TYPE_NAME, len(self.args), 2)

        sda = self.get_pin(0)
        scl = self.get_pin(1)
        if len(self.args) == 3:
            addr = self.get_arg(2, int)
            if addr.arg < 0:
                raise ProfileEntryError(addr.pos, "I2C address cannot be negative")
            addr = addr.arg
        else:
            addr = self.default_addr
        entry = [self.component_id, sda, scl, addr]
        profile.append(entry)


class ID:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return f"ID({self.name})"


class Arg:
    def __init__(self, pos, arg):
        self.pos = pos
        self.arg = arg


class ComponentFactory:
    def __init__(self, name, details):
        self.name = name
        self.component_id = details['id']


class GPIOSwitchFactory(ComponentFactory):
    def __init__(self, name, details):
        details['id'] = DeviceProfile_EntryType_GPIOSwitch
        super().__init__(name, details)
        self.switch_type = details['switchType']

    def __call__(self, pos, args):
        return Switch(self.switch_type, pos, args)


class GPIORelayFactory(ComponentFactory):
    def __init__(self, name, details):
        details['id'] = DeviceProfile_EntryType_Relay
        super().__init__(name, details)
        self.relay_type = details['relayType']

    def __call__(self, pos, args):
        return BaseRelay(self.relay_type, pos, args)


class GPIOPinComponentFactory(ComponentFactory):
    def __call__(self, pos, args):
        return GPIOPinComponent(self.name, self.component_id, pos, args)


class I2CDeviceFactory(ComponentFactory):
    def __init__(self, name, details):
        super().__init__(name, details)
        self.addr = details['addr']

    def __call__(self, pos, args):
        return I2cDevice(self.name, self.component_id, self.addr, pos, args)


factories = {
    'gpio_pin': GPIOPinComponentFactory,
    'i2c': I2CDeviceFactory,
    'gpio_switch': GPIOSwitchFactory,
    'gpio_relay': GPIORelayFactory
}

components = {}
with open(os.path.join(os.path.dirname(__file__), "components.yaml")) as fp:
    for name, details in yaml.safe_load(fp).items():
        component_type = details['type']
        if component_type not in factories:
            raise RuntimeError(f"Unknown componnet type {component_type} for {name}")
        components[name] = factories[component_type](name, details)


