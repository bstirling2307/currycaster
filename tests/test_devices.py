from cc.devices import list_output_devices, resolve_output


HOSTAPIS = [
    {"name": "MME"},
    {"name": "Windows DirectSound"},
    {"name": "Windows WASAPI"},
]


def _device(index, name, hostapi, outputs):
    return {"index": index, "name": name, "hostapi": hostapi, "max_output_channels": outputs}


def test_wasapi_outputs_hide_legacy_aliases_and_inputs():
    devices = [
        _device(0, "Speakers", 0, 2),
        _device(1, "Speakers", 1, 2),
        _device(2, "Speakers", 2, 2),
        _device(3, "Microphone", 2, 0),
        _device(4, "Headphones", 2, 2),
    ]
    listed = list_output_devices((devices, HOSTAPIS))
    assert [item.name for item in listed] == ["Speakers", "Headphones"]
    assert listed[0].index == 2
    assert "WASAPI" in listed[0].description
    assert resolve_output("Headphones", listed) == 4


def test_duplicate_wasapi_names_are_disambiguated():
    devices = [
        _device(2, "Speakers", 2, 2),
        _device(5, "Speakers", 2, 2),
    ]
    listed = list_output_devices((devices, HOSTAPIS))
    assert len(listed) == 2
    assert len({item.name for item in listed}) == 2
    assert resolve_output(listed[1].name, listed) == 5


def test_all_outputs_are_listed_when_wasapi_is_absent():
    devices = [_device(0, "Default", 0, 2)]
    hostapis = [{"name": "ALSA"}]
    listed = list_output_devices((devices, hostapis))
    assert [item.name for item in listed] == ["Default"]


def test_live_enumeration_returns_a_list():
    listed = list_output_devices()
    assert isinstance(listed, list)
