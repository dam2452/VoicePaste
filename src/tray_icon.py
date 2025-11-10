import pystray
import threading
from PIL import Image, ImageDraw
from typing import Callable


class TrayIcon:
    def __init__(self, on_quit: Callable):
        self.on_quit = on_quit
        self.icon = None
        self.status = "idle"
        self.thread = None

    def create_icon_image(self, color: str = "green") -> Image.Image:
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)

        if color == "green":
            fill_color = (34, 139, 34)
        elif color == "red":
            fill_color = (220, 20, 60)
        elif color == "orange":
            fill_color = (255, 140, 0)
        else:
            fill_color = (128, 128, 128)

        draw.ellipse([8, 8, 56, 56], fill=fill_color, outline='black')
        return image

    def start(self):
        menu = pystray.Menu(
            pystray.MenuItem("VoicePaste", lambda: None, enabled=False),
            pystray.MenuItem("Status: Ready", self._get_status, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit_action)
        )

        self.icon = pystray.Icon(
            "VoicePaste",
            self.create_icon_image("green"),
            "VoicePaste - Ready",
            menu
        )
        self.thread = threading.Thread(target=self.icon.run, daemon=True)
        self.thread.start()

    def update_status(self, status: str):
        self.status = status
        if self.icon:
            if status == "recording":
                self.icon.icon = self.create_icon_image("red")
                self.icon.title = "VoicePaste - Recording"
            elif status == "processing":
                self.icon.icon = self.create_icon_image("orange")
                self.icon.title = "VoicePaste - Processing"
            else:
                self.icon.icon = self.create_icon_image("green")
                self.icon.title = "VoicePaste - Ready"

    def _get_status(self):
        return f"Status: {self.status.capitalize()}"

    def _quit_action(self):
        if self.icon:
            self.icon.stop()
        self.on_quit()

    def stop(self):
        if self.icon:
            self.icon.stop()
