import unittest
from unittest import mock

import controller_backend


class XInputControllerBackendTests(unittest.TestCase):
    def setUp(self):
        self.backend = controller_backend.XInputControllerBackend()

    @mock.patch.object(
        controller_backend.XInput,
        "get_connected",
        return_value=(False, True, False, False),
    )
    def test_lists_connected_xinput_slots(self, _get_connected):
        self.assertEqual(
            self.backend.list_devices(),
            [controller_backend.ControllerDevice("xinput:1", "Controller 2")],
        )

    @mock.patch.object(
        controller_backend.XInput,
        "get_trigger_values",
        return_value=(0.75, 0.0),
    )
    @mock.patch.object(
        controller_backend.XInput,
        "get_button_values",
        return_value={"A": True, "B": False, "START": True},
    )
    @mock.patch.object(controller_backend.XInput, "get_state", return_value=object())
    @mock.patch.object(
        controller_backend.XInput,
        "get_connected",
        return_value=(True, False, False, False),
    )
    def test_reads_buttons_and_triggers(
        self, _get_connected, _get_state, _get_buttons, _get_triggers
    ):
        self.assertEqual(
            self.backend.get_pressed_buttons("xinput:0"), ["A", "START", "LT"]
        )

    @mock.patch.object(
        controller_backend.XInput,
        "get_connected",
        return_value=(False, False, False, False),
    )
    def test_disconnected_controller_returns_none(self, _get_connected):
        self.assertIsNone(self.backend.get_pressed_buttons("xinput:0"))


class BackendSelectionTests(unittest.TestCase):
    @mock.patch.object(
        controller_backend,
        "SDL3ControllerBackend",
        side_effect=FileNotFoundError("not installed"),
    )
    def test_falls_back_to_xinput_without_sdl3(self, _sdl_backend):
        backend = controller_backend.create_controller_backend("C:\\missing")
        self.assertIsInstance(backend, controller_backend.XInputControllerBackend)


if __name__ == "__main__":
    unittest.main()
