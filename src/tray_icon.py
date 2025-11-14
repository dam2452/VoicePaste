import pystray
import threading
from PIL import Image, ImageDraw
from typing import Callable


class TrayIcon:
    def __init__(
        self,
        on_quit: Callable,
        on_toggle_recording: Callable = None,
        on_toggle_keep_model: Callable = None,
        get_model_status: Callable = None,
        on_transcribe_youtube: Callable = None,
        on_transcribe_file: Callable = None
    ):
        self.on_quit = on_quit
        self.on_toggle_recording = on_toggle_recording
        self.on_toggle_keep_model = on_toggle_keep_model
        self.get_model_status = get_model_status
        self.on_transcribe_youtube = on_transcribe_youtube
        self.on_transcribe_file = on_transcribe_file
        self.icon = None
        self.status = "idle"
        self.thread = None
        self.keep_model_enabled = False

    def create_icon_image(self, status: str = "idle") -> Image.Image:
        size = 512
        image = Image.new('RGBA', (size, size), color=(255, 255, 255, 0))
        draw = ImageDraw.Draw(image)

        if status == "idle":
            self._draw_microphone(draw, size, (76, 175, 80))
        elif status == "recording":
            self._draw_microphone(draw, size, (244, 67, 54))
            self._draw_sound_waves(draw, size, (244, 67, 54))
        elif status == "downloading":
            self._draw_microphone(draw, size, (156, 39, 176))
            self._draw_download_arrow(draw, size, (156, 39, 176))
        elif status == "processing":
            self._draw_microphone(draw, size, (33, 150, 243))
            self._draw_clipboard(draw, size, (33, 150, 243))

        return image

    @staticmethod
    def _draw_microphone(draw: ImageDraw.ImageDraw, size: int, color: tuple):
        cx, cy = size // 2, size // 2

        mic_width = int(size * 0.50)
        mic_height = int(size * 0.58)
        top_y = cy - mic_height // 2 - int(size * 0.04)

        draw.rounded_rectangle(
            [cx - mic_width // 2, top_y, cx + mic_width // 2, top_y + mic_height],
            radius=mic_width // 2,
            fill=color
        )

        body_y = top_y + mic_height
        arc_width = int(size * 0.08)
        draw.arc(
            [cx - int(mic_width * 1.1), body_y - int(size * 0.02),
             cx + int(mic_width * 1.1), body_y + int(mic_height * 0.35)],
            start=0, end=180, fill=color, width=arc_width
        )

        stand_bottom = cy + mic_height // 2 + int(size * 0.12)
        stand_width = int(size * 0.06)
        draw.line([cx, body_y + int(mic_height * 0.15), cx, stand_bottom],
                 fill=color, width=stand_width)
        draw.line([cx - int(mic_width * 0.6), stand_bottom,
                  cx + int(mic_width * 0.6), stand_bottom],
                 fill=color, width=stand_width)

    @staticmethod
    def _draw_sound_waves(draw: ImageDraw.ImageDraw, size: int, color: tuple):
        cx, cy = size // 2, size // 2

        wave_offset = int(size * 0.38)
        wave_width = int(size * 0.05)

        wave_sizes = [
            (int(size * 0.06), int(size * 0.12)),
            (int(size * 0.08), int(size * 0.18)),
            (int(size * 0.06), int(size * 0.12))
        ]

        for i, (w, h) in enumerate(wave_sizes):
            x_left = cx - wave_offset - i * int(size * 0.05)
            x_right = cx + wave_offset + i * int(size * 0.05)

            draw.arc([x_left - w, cy - h, x_left + w, cy + h],
                    start=270, end=90, fill=color, width=wave_width)
            draw.arc([x_right - w, cy - h, x_right + w, cy + h],
                    start=90, end=270, fill=color, width=wave_width)

    @staticmethod
    def _draw_download_arrow(draw: ImageDraw.ImageDraw, size: int, color: tuple):
        arrow_size = int(size * 0.3)
        arrow_x = size - arrow_size - int(size * 0.05)
        arrow_y = size - arrow_size - int(size * 0.05)
        arrow_width = int(size * 0.06)

        shaft_top = arrow_y + int(arrow_size * 0.2)
        shaft_bottom = arrow_y + int(arrow_size * 0.6)
        shaft_left = arrow_x + arrow_size // 2 - arrow_width // 2
        shaft_right = arrow_x + arrow_size // 2 + arrow_width // 2

        draw.rectangle([shaft_left, shaft_top, shaft_right, shaft_bottom], fill=color)

        head_points = [
            (arrow_x + arrow_size // 2, arrow_y + int(arrow_size * 0.8)),
            (arrow_x + int(arrow_size * 0.2), shaft_bottom),
            (arrow_x + int(arrow_size * 0.8), shaft_bottom)
        ]
        draw.polygon(head_points, fill=color)

    @staticmethod
    def _draw_clipboard(draw: ImageDraw.ImageDraw, size: int, color: tuple):
        clip_size = int(size * 0.36)
        clip_x = size - clip_size - int(size * 0.04)
        clip_y = size - clip_size - int(size * 0.04)
        border_width = int(size * 0.05)
        radius = int(size * 0.03)

        draw.rounded_rectangle(
            [clip_x, clip_y, clip_x + clip_size, clip_y + clip_size],
            radius=radius,
            outline=color,
            width=border_width
        )

        line_y1 = clip_y + clip_size // 3
        line_y2 = clip_y + 2 * clip_size // 3
        margin = int(size * 0.05)
        line_width = int(size * 0.04)

        draw.line([clip_x + margin, line_y1, clip_x + clip_size - margin, line_y1],
                 fill=color, width=line_width)
        draw.line([clip_x + margin, line_y2, clip_x + clip_size - margin, line_y2],
                 fill=color, width=line_width)

    def start(self):
        def create_menu():
            return pystray.Menu(
                pystray.MenuItem("VoicePaste - Voice to Text", lambda: None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(self._get_status_text, lambda: None, enabled=False),
                pystray.MenuItem(self._get_model_location, lambda: None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Record (Shift+V)",
                    self._toggle_recording_action,
                    enabled=bool(self.on_toggle_recording)
                ),
                pystray.MenuItem(
                    "Transcribe YouTube URL... (Shift+Y)",
                    self._transcribe_youtube_action,
                    enabled=bool(self.on_transcribe_youtube)
                ),
                pystray.MenuItem(
                    "Transcribe File... (Shift+F)",
                    self._transcribe_file_action,
                    enabled=bool(self.on_transcribe_file)
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Keep Model in Memory",
                    self._toggle_keep_model_action,
                    checked=lambda _: self.keep_model_enabled,
                    enabled=bool(self.on_toggle_keep_model)
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", self._quit_action)
            )

        self.icon = pystray.Icon(
            "VoicePaste",
            self.create_icon_image("idle"),
            "VoicePaste - Ready",
            menu=create_menu()
        )
        self.thread = threading.Thread(target=self.icon.run, daemon=True)
        self.thread.start()

    def update_status(self, status: str):
        self.status = status
        if self.icon:
            if status == "recording":
                self.icon.icon = self.create_icon_image("recording")
                self.icon.title = "VoicePaste - Recording"
            elif status == "downloading":
                self.icon.icon = self.create_icon_image("downloading")
                self.icon.title = "VoicePaste - Downloading"
            elif status == "processing":
                self.icon.icon = self.create_icon_image("processing")
                self.icon.title = "VoicePaste - Processing"
            else:
                self.icon.icon = self.create_icon_image("idle")
                self.icon.title = "VoicePaste - Ready"

    def _get_status_text(self, _=None):
        status_map = {
            "idle": "Ready",
            "recording": "Recording...",
            "downloading": "Downloading...",
            "processing": "Processing..."
        }
        status = status_map.get(self.status, self.status.capitalize())
        icon = {"idle": "✓", "recording": "●", "downloading": "⬇", "processing": "⚙"}.get(self.status, "○")
        return f"{icon} Status: {status}"

    def _get_model_location(self, _=None):
        if self.get_model_status:
            location = self.get_model_status()
            if "VRAM" in location:
                icon = "⚡"
            elif "RAM" in location:
                icon = "💾"
            else:
                icon = "○"
            return f"{icon} Model: {location}"
        return "○ Model: Unknown"

    def _toggle_recording_action(self, _=None):
        if self.on_toggle_recording:
            self.on_toggle_recording()

    def _toggle_keep_model_action(self, _=None):
        if self.on_toggle_keep_model:
            self.keep_model_enabled = not self.keep_model_enabled
            self.on_toggle_keep_model()
            if self.icon:
                self.icon.update_menu()

    def _transcribe_youtube_action(self, _=None):
        if self.on_transcribe_youtube:
            self.on_transcribe_youtube()

    def _transcribe_file_action(self, _=None):
        if self.on_transcribe_file:
            self.on_transcribe_file()

    def _quit_action(self, _=None):
        if self.icon:
            self.icon.stop()
        self.on_quit()

    def stop(self):
        if self.icon:
            self.icon.stop()
