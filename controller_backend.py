"""Game controller input backends used by PC-Console Switcher.

SDL3 is preferred because Steam Controllers are HID devices and are not exposed
through XInput.  XInput remains as a fallback for machines without SDL3.
"""

from __future__ import annotations

import ctypes
import logging
import os
from dataclasses import dataclass

import XInput


SDL_INIT_GAMEPAD = 0x00002000
VALVE_VENDOR_ID = 0x28DE


@dataclass(frozen=True)
class ControllerDevice:
    key: str
    name: str
    vendor_id: int = 0
    product_id: int = 0


class SDL3ControllerBackend:
    """Small ctypes wrapper around SDL3's cross-vendor gamepad API."""

    name = "SDL3 (HID + XInput)"

    # SDL's positional face button names are converted to the Xbox-style names
    # already used by existing config.json files.
    BUTTONS = {
        0: "A",
        1: "B",
        2: "X",
        3: "Y",
        4: "BACK",
        5: "GUIDE",
        6: "START",
        7: "LEFT_THUMB",
        8: "RIGHT_THUMB",
        9: "LEFT_SHOULDER",
        10: "RIGHT_SHOULDER",
        11: "DPAD_UP",
        12: "DPAD_DOWN",
        13: "DPAD_LEFT",
        14: "DPAD_RIGHT",
        15: "MISC1",
        16: "RIGHT_PADDLE1",
        17: "LEFT_PADDLE1",
        18: "RIGHT_PADDLE2",
        19: "LEFT_PADDLE2",
        20: "TOUCHPAD",
        21: "MISC2",
        22: "MISC3",
        23: "MISC4",
        24: "MISC5",
        25: "MISC6",
    }
    LEFT_TRIGGER_AXIS = 4
    RIGHT_TRIGGER_AXIS = 5
    TRIGGER_THRESHOLD = 16384

    def __init__(self, dll_candidates):
        self.dll_path = self._find_dll(dll_candidates)
        self.sdl = ctypes.CDLL(self.dll_path)
        self._configure_api()

        # The switcher spends almost all its time hidden in the notification
        # area, so gamepad events must remain enabled without keyboard focus.
        self.sdl.SDL_SetHint(
            b"SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", b"1"
        )
        if not self.sdl.SDL_Init(SDL_INIT_GAMEPAD):
            raise RuntimeError(self._error("SDL_Init(SDL_INIT_GAMEPAD) failed"))

        self.handles = {}
        logging.info("Controller backend: SDL3 (%s)", self.dll_path)

    @staticmethod
    def _find_dll(candidates):
        checked = []
        for candidate in candidates:
            if not candidate:
                continue
            candidate = os.path.abspath(candidate)
            if candidate in checked:
                continue
            checked.append(candidate)
            if os.path.isfile(candidate):
                return candidate
        raise FileNotFoundError("SDL3.dll not found; checked: " + ", ".join(checked))

    def _configure_api(self):
        sdl = self.sdl
        sdl.SDL_SetHint.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        sdl.SDL_SetHint.restype = ctypes.c_bool
        sdl.SDL_Init.argtypes = [ctypes.c_uint32]
        sdl.SDL_Init.restype = ctypes.c_bool
        sdl.SDL_GetError.restype = ctypes.c_char_p
        sdl.SDL_UpdateGamepads.argtypes = []
        sdl.SDL_UpdateGamepads.restype = None
        sdl.SDL_GetGamepads.argtypes = [ctypes.POINTER(ctypes.c_int)]
        sdl.SDL_GetGamepads.restype = ctypes.POINTER(ctypes.c_uint32)
        sdl.SDL_GetGamepadNameForID.argtypes = [ctypes.c_uint32]
        sdl.SDL_GetGamepadNameForID.restype = ctypes.c_char_p
        sdl.SDL_GetGamepadVendorForID.argtypes = [ctypes.c_uint32]
        sdl.SDL_GetGamepadVendorForID.restype = ctypes.c_uint16
        sdl.SDL_GetGamepadProductForID.argtypes = [ctypes.c_uint32]
        sdl.SDL_GetGamepadProductForID.restype = ctypes.c_uint16
        sdl.SDL_OpenGamepad.argtypes = [ctypes.c_uint32]
        sdl.SDL_OpenGamepad.restype = ctypes.c_void_p
        sdl.SDL_CloseGamepad.argtypes = [ctypes.c_void_p]
        sdl.SDL_GamepadConnected.argtypes = [ctypes.c_void_p]
        sdl.SDL_GamepadConnected.restype = ctypes.c_bool
        sdl.SDL_GetGamepadButton.argtypes = [ctypes.c_void_p, ctypes.c_int]
        sdl.SDL_GetGamepadButton.restype = ctypes.c_bool
        sdl.SDL_GetGamepadAxis.argtypes = [ctypes.c_void_p, ctypes.c_int]
        sdl.SDL_GetGamepadAxis.restype = ctypes.c_int16
        sdl.SDL_free.argtypes = [ctypes.c_void_p]
        sdl.SDL_QuitSubSystem.argtypes = [ctypes.c_uint32]
        sdl.SDL_QuitSubSystem.restype = None

    def _error(self, prefix):
        raw_error = self.sdl.SDL_GetError()
        detail = raw_error.decode("utf-8", errors="replace") if raw_error else "unknown error"
        return f"{prefix}: {detail}"

    def list_devices(self):
        self.sdl.SDL_UpdateGamepads()
        count = ctypes.c_int()
        ids = self.sdl.SDL_GetGamepads(ctypes.byref(count))
        if not ids and count.value:
            raise RuntimeError(self._error("SDL_GetGamepads failed"))

        active_ids = set()
        devices = []
        try:
            for index in range(count.value):
                joystick_id = int(ids[index])
                active_ids.add(joystick_id)
                raw_name = self.sdl.SDL_GetGamepadNameForID(joystick_id)
                name = raw_name.decode("utf-8", errors="replace") if raw_name else "Controller"
                vendor_id = int(self.sdl.SDL_GetGamepadVendorForID(joystick_id))
                product_id = int(self.sdl.SDL_GetGamepadProductForID(joystick_id))
                key = f"sdl:{joystick_id}"

                if key not in self.handles:
                    handle = self.sdl.SDL_OpenGamepad(joystick_id)
                    if handle:
                        self.handles[key] = handle
                        logging.info(
                            "Controller connected: %s (VID_%04X&PID_%04X, %s)",
                            name,
                            vendor_id,
                            product_id,
                            key,
                        )
                    else:
                        logging.error(self._error(f"Could not open {name}"))
                if key in self.handles:
                    devices.append(ControllerDevice(key, name, vendor_id, product_id))
        finally:
            if ids:
                self.sdl.SDL_free(ids)

        for key in list(self.handles):
            joystick_id = int(key.split(":", 1)[1])
            if joystick_id not in active_ids:
                self.sdl.SDL_CloseGamepad(self.handles.pop(key))
                logging.info("Controller disconnected: %s", key)
        return devices

    def get_pressed_buttons(self, key):
        handle = self.handles.get(key)
        if not handle or not self.sdl.SDL_GamepadConnected(handle):
            return None

        self.sdl.SDL_UpdateGamepads()
        pressed = [
            name
            for button, name in self.BUTTONS.items()
            if self.sdl.SDL_GetGamepadButton(handle, button)
        ]
        if self.sdl.SDL_GetGamepadAxis(handle, self.LEFT_TRIGGER_AXIS) > self.TRIGGER_THRESHOLD:
            pressed.append("LT")
        if self.sdl.SDL_GetGamepadAxis(handle, self.RIGHT_TRIGGER_AXIS) > self.TRIGGER_THRESHOLD:
            pressed.append("RT")
        return pressed

    def describe(self):
        return f"SDL3 ({self.dll_path})"

    def close(self):
        for handle in self.handles.values():
            self.sdl.SDL_CloseGamepad(handle)
        self.handles.clear()
        self.sdl.SDL_QuitSubSystem(SDL_INIT_GAMEPAD)


class XInputControllerBackend:
    """Compatibility fallback used when SDL3 is not installed with Steam."""

    name = "XInput fallback"

    def list_devices(self):
        return [
            ControllerDevice(f"xinput:{index}", f"Controller {index + 1}")
            for index, connected in enumerate(XInput.get_connected())
            if connected
        ]

    def get_pressed_buttons(self, key):
        index = int(key.split(":", 1)[1])
        if not XInput.get_connected()[index]:
            return None
        state = XInput.get_state(index)
        buttons = XInput.get_button_values(state)
        pressed = [button for button, value in buttons.items() if value]
        left_trigger, right_trigger = XInput.get_trigger_values(state)
        if left_trigger > 0.5:
            pressed.append("LT")
        if right_trigger > 0.5:
            pressed.append("RT")
        return pressed

    def describe(self):
        return "XInput fallback"

    def close(self):
        pass


def create_controller_backend(app_dir, steam_path=""):
    steam_dir = os.path.dirname(steam_path) if steam_path else ""
    candidates = [
        os.path.join(app_dir, "SDL3.dll"),
        os.path.join(steam_dir, "SDL3.dll") if steam_dir else "",
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Steam", "SDL3.dll"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Steam", "SDL3.dll"),
    ]
    try:
        return SDL3ControllerBackend(candidates)
    except Exception as exc:
        logging.warning("SDL3 controller backend unavailable: %s", exc, exc_info=True)
        logging.info("Controller backend: XInput fallback")
        return XInputControllerBackend()
