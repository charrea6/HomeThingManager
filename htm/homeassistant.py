from typing import List, Tuple, Dict, Iterable
from .deviceinfo import TopicEntry, TopicInfo, MessageType

template_config = {
    MessageType.CELSIUS: dict(device_class="temperature", unit_of_measurement="°C"),
    MessageType.PERCENT_RH: dict(device_class="humidity", unit_of_measurement="% RH"),
    MessageType.KPA: dict(device_class="pressure", unit_of_measurement="kPa")
}


def get_path(component: str, device_uuid: str, entry: TopicEntry, info: TopicInfo):
    node_id = device_uuid
    if info.path:
        object_id = f'{entry.path}_{info.path}'
    else:
        object_id = entry.path
    return f"homeassistant/{component}/{node_id}/{object_id}/config"


def handle_sensor(device_uuid: str, entry: TopicEntry, configs: List[Tuple[str, Dict]]) -> None:
    for info in entry.pubs:
        path = get_path("sensor", device_uuid, entry, info)
        config = dict(device={"identifiers": device_uuid}, state_topic=info.get_path(device_uuid, entry),
                      unique_id=f"{device_uuid}/{entry.path}/{info.path}")
        config.update(template_config.get(info.message_type, {}))
        configs.append((path, config))


def handle_controller(device_uuid: str, entry: TopicEntry, configs: List[Tuple[str, Dict]]) -> None:
    pass


def get_home_assistant_configs(device_uuid: str, entries: Iterable[TopicEntry]) -> List[Tuple[str, Dict]]:
    configs = []
    for entry in entries:
        if entry.subs:
            handle_controller(device_uuid, entry, configs)
        else:
            handle_sensor(device_uuid, entry, configs)
    return configs
