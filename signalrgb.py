import time
import driver
import time
import pystray
from PIL import Image, ImageFont, ImageDraw
from io import BytesIO
from mss import mss
import queue
from threading import Thread
from utils import debug, timing
import json
import psutil
import sys
import os
from workers import FrameWriter
from http.server import BaseHTTPRequestHandler, HTTPServer
import base64
from socketserver import ThreadingMixIn
import shutil
import socketio
import requests

PORT = 30003
BASE_PATH = "."
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BASE_PATH = sys._MEIPASS

FONT_FILE = os.path.join(BASE_PATH, "fonts/Rubik-Bold.ttf")
APP_ICON = os.path.join(BASE_PATH, "images/plugin.png")

MIN_SPEED = 2
BASE_SPEED = 18

import ctypes.wintypes


stats = {
    "cpu": 0,
    "pump": 0,
    "liquid": 0,
}

# dyanmicPalette test
MIN_COLORS = 64
colors = MIN_COLORS * 2


lcd = driver.KrakenLCD()
lcd.setupStream()

pluginInstalled = False
try:
    CSIDL_PERSONAL = 5  # My Documents
    SHGFP_TYPE_CURRENT = 0  # Get current, not default value
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(
        None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf
    )
    shutil.copytree(
        os.path.join(BASE_PATH, "SignalRGBPlugin"),
        os.path.join(buf.value, "WhirlwindFX/Plugins/KrakenLCDBridge/"),
        dirs_exist_ok=True,
    )
    print("Successfully installed SignalRGB plugin")
    pluginInstalled = True

except Exception:
    print("Could not automatically install SignalRGB plugin")


ThreadingMixIn.daemon_threads = True


class RawProducer(Thread):
    def __init__(self, rawBuffer: queue.Queue):
        Thread.__init__(self, name="RawProducer")
        self.daemon = True
        self.rawBuffer = rawBuffer

    def run(self):
        debug("Server worker started")
        rawBuffer = self.rawBuffer
        lastFrame = time.time()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def _set_headers(self, contentType="application/json"):
                self.send_response(200)
                self.send_header("Content-type", contentType)
                self.end_headers()

            def do_HEAD(self):
                self._set_headers()

            def do_GET(self):
                if (
                    self.path == "/images/2023elite.png"
                    or self.path == "/images/2023.png"
                    or self.path == "/images/z3.png"
                    or self.path == "/images/plugin.png"
                ):
                    file = open(BASE_PATH + self.path, "rb")
                    data = file.read()
                    file.close()
                    self._set_headers("image/png")
                    self.wfile.write(data)
                else:
                    self._set_headers()
                    self.wfile.write(bytes(json.dumps(lcd.getInfo()), "utf-8"))

            def do_POST(self):
                nonlocal lastFrame
                if self.path == "/brightness":
                    postData = self.rfile.read(
                        int(self.headers["Content-Length"] or "0")
                    )
                    data = json.loads(postData.decode("utf-8"))
                    lcd.setBrightness(data["brightness"])
                if self.path == "/frame":
                    postData = self.rfile.read(
                        int(self.headers["Content-Length"] or "0")
                    )
                    rawTime = time.time() - lastFrame
                    rawBuffer.put((postData, rawTime))
                    lastFrame = time.time()
                self._set_headers()

        class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
            pass

        server_address = ("", PORT)
        server = ThreadingSimpleServer(server_address, Handler)
        # httpd.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        server.serve_forever()


def download_image(url):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode('utf-8')
        else:
            debug(f"Failed to download image, status code: {response.status_code}")
            return None
    except Exception as e:
        debug(f"Exception occurred while downloading image: {e}")
        return None

class OverlayProducer(Thread):
    def __init__(self, rawBuffer: queue.Queue, frameBuffer: queue.Queue):
        Thread.__init__(self, name="OverlayProducer")
        self.daemon = True
        self.rawBuffer = rawBuffer
        self.frameBuffer = frameBuffer
        self.lastAngle = 0
        self.circleImg = Image.new("RGBA", lcd.resolution, (0, 0, 0, 0))
        self.fonts = {
            "titleFontSize": 10,
            "sensorFontSize": 100,
            "sensorLabelFontSize": 10,
            "fontTitle": ImageFont.truetype(FONT_FILE, 10),
            "fontSensor": ImageFont.truetype(FONT_FILE, 100),
            "fontSensorLabel": ImageFont.truetype(FONT_FILE, 10),
            "fontDegree": ImageFont.truetype(FONT_FILE, 10 // 3),
        }

        #Update font paths for different weights
        self.MUSIC_FONTS = {
            'bold': os.path.join(BASE_PATH, "fonts/Figtree-Bold.ttf"),
            'semibold': os.path.join(BASE_PATH, "fonts/Figtree-SemiBold.ttf"),
            'medium': os.path.join(BASE_PATH, "fonts/Figtree-Medium.ttf"),
            'regular': os.path.join(BASE_PATH, "fonts/Figtree-Regular.ttf"),
            'light': os.path.join(BASE_PATH, "fonts/Figtree-Light.ttf")
        }
    
            # Initialize fonts with different weights and sizes
        self.music_fonts = {
            'title': ImageFont.truetype(self.MUSIC_FONTS['bold'], size=36),      # Bold weight for title
            'artist': ImageFont.truetype(self.MUSIC_FONTS['semibold'], size=28), # Semibold for artist
            'album': ImageFont.truetype(self.MUSIC_FONTS['regular'], size=20)     # Regular for album
        }

        self.musicInfo = {
            'title': '',
            'artist': '',
            'album': '',
            'image': None,
        }

        self.socket = None
        self.appToken = None  # Set the app token if required

    def updateFonts(self, data):
        if data["titleFontSize"] != self.fonts["titleFontSize"]:
            data["titleFontSize"] = data["titleFontSize"]
            self.fonts["fontTitle"] = ImageFont.truetype(
                FONT_FILE, data["titleFontSize"]
            )
        if data["sensorFontSize"] != self.fonts["sensorFontSize"]:
            data["sensorFontSize"] = data["sensorFontSize"]
            self.fonts["fontSensor"] = ImageFont.truetype(
                FONT_FILE, data["sensorFontSize"]
            )
            self.fonts["fontDegree"] = ImageFont.truetype(
                FONT_FILE, data["sensorFontSize"] // 3
            )
        if data["sensorLabelFontSize"] != self.fonts["sensorLabelFontSize"]:
            data["sensorLabelFontSize"] = data["sensorLabelFontSize"]
            self.fonts["fontSensorLabel"] = ImageFont.truetype(
                FONT_FILE, data["sensorLabelFontSize"]
            )

    def run(self):
        debug("Overlay converter worker started")
        while True:
            if self.frameBuffer.full():
                time.sleep(0.001)
                continue

            postData, rawTime = self.rawBuffer.get()
            data = json.loads(postData.decode("utf-8"))
            self.appToken = data.get('musicToken') if data.get('musicOverlay') else None  # Assign musicToken only if musicOverlay is enabled
            self.addOverlay(postData, rawTime)
            if data.get('musicOverlay'):
                if not self.socket:
                    self.setupCiderConnection()
            else:
                if self.socket:
                    self.socket.disconnect()
                    self.socket = None

    def setupCiderConnection(self):
        if not self.appToken:
            debug("Music token is missing. Cannot establish Cider connection.")
            return
        self.socket = socketio.Client()
        @self.socket.on('API:Playback')
        def on_playback_update(data):
            if (data.get('type') == 'playbackStatus.nowPlayingItemDidChange'):
                self.handlePlaybackUpdate(data)
        try:
            self.socket.connect('http://localhost:10767', auth={'token': self.appToken})
            response = requests.get(
                'http://localhost:10767/api/v1/playback/now-playing',
                headers={'apptoken': self.appToken} if self.appToken else {}
            )
            if response.status_code == 200:
                print('Connected to Cider successfully')
                self.updateMusicInfo(response.json().get('info'))
        except Exception as e:
            print('Error connecting to Cider:', e)

    def handlePlaybackUpdate(self, data):
        self.updateMusicInfo(data.get('data'))

    def updateMusicInfo(self, info):
        if self.appToken and info:
            self.musicInfo['title'] = info.get('name', 'No Track')
            self.musicInfo['artist'] = info.get('artistName', '')
            self.musicInfo['album'] = info.get('albumName', '')
            artwork_url = info.get('artwork', {}).get('url')
            if artwork_url:
                artwork_url = artwork_url.replace('512x512bb', '1024x1024bb').replace('{w}x{h}bb', '1024x1024bb')
                try:
                    response = requests.get(artwork_url)
                    self.musicInfo['image'] = Image.open(BytesIO(response.content)).convert('RGBA')
                    self.musicInfo['image'] = self.musicInfo['image'].resize(
                        (lcd.resolution.width, lcd.resolution.height),
                        Image.Resampling.LANCZOS
                    )
                except Exception as e:
                    print("Error loading artwork:", e)
                    self.musicInfo['image'] = None
            else:
                print("No artwork found")
                self.musicInfo = {
                    'title': 'No Track',
                    'artist': '',
                    'album': '',
                    'image': None,
                }
        else:
            # Reset musicInfo if musicOverlay is disabled
            self.musicInfo = {
                'title': '',
                'artist': '',
                'album': '',
                'image': None,
            }

    @timing
    def parseImage(self, data):
        raw = base64.b64decode(data["raw"])

        return (
            Image.open(BytesIO(raw))
            .convert("RGBA")
            .resize(
                lcd.resolution,
                Image.Resampling.LANCZOS,
            )
        )

    @timing
    def renderOverlay(self, data):
        alpha = 255
        if data["composition"] == "OVERLAY":
            alpha = round((100 - data["overlayTransparency"]) * 255 / 100)
        overlay = Image.new("RGBA", data["size"], (0, 0, 0, 0))
        overlayCanvas = ImageDraw.Draw(overlay)

        if data["spinner"] == "CPU" or data["spinner"] == "PUMP":
            bands = list(self.circleImg.split())
            bands[3] = bands[3].point(lambda x: round(x / 1.1) if x > 10 else 0)
            self.circleImg = Image.merge(self.circleImg.mode, bands)
            circleCanvas = ImageDraw.Draw(self.circleImg)

            angle = MIN_SPEED + BASE_SPEED * stats[data["spinner"].lower()] / 100

            newAngle = self.lastAngle + angle
            circleCanvas.arc(
                [(0, 0), lcd.resolution],
                fill=(255, 255, 255, round(alpha / 1.05)),
                width=lcd.resolution.width // 20,
                start=self.lastAngle,
                end=self.lastAngle + angle / 2,
            )
            circleCanvas.arc(
                [(0, 0), lcd.resolution],
                fill=(255, 255, 255, alpha),
                width=lcd.resolution.width // 20,
                start=self.lastAngle + angle / 2,
                end=newAngle,
            )
            self.lastAngle = newAngle
            overlay.paste(self.circleImg)

        if data["spinner"] == "STATIC":
            overlayCanvas.ellipse(
                [(0, 0), lcd.resolution],
                outline=(255, 255, 255, alpha),
                width=lcd.resolution.width // 20,
            )
        if data["textOverlay"]:
            self.updateFonts(data)
            overlayCanvas.text(
                (lcd.resolution.width // 2, lcd.resolution.height // 5),
                text=data["titleText"],
                anchor="mm",
                align="center",
                font=self.fonts["fontTitle"],
                fill=(255, 255, 255, alpha),
            )
            overlayCanvas.text(
                (lcd.resolution.width // 2, lcd.resolution.height // 2),
                text="{:.0f}".format(stats["liquid"]),
                anchor="mm",
                align="center",
                font=self.fonts["fontSensor"],
                fill=(255, 255, 255, alpha),
            )
            textBbox = overlayCanvas.textbbox(
                (lcd.resolution.width // 2, lcd.resolution.height // 2),
                text="{:.0f}".format(stats["liquid"]),
                anchor="mm",
                align="center",
                font=self.fonts["fontSensor"],
            )
            overlayCanvas.text(
                ((textBbox[2], textBbox[1])),
                text="°",
                anchor="lt",
                align="center",
                font=self.fonts["fontDegree"],
                fill=(255, 255, 255, alpha),
            )
            overlayCanvas.text(
                (lcd.resolution.width // 2, 4 * lcd.resolution.height // 5),
                text="Liquid",
                anchor="mm",
                align="center",
                font=self.fonts["fontSensorLabel"],
                fill=(255, 255, 255, alpha),
            )
        if data.get("musicOverlay"):
            # Screen dimensions
            width, height = 640, 640
        
            if self.musicInfo['image']:
                # Make album art 60% of screen width/height
                art_size = 384
                # Position it with proper spacing from top (15% from top)
                top_padding = int(height * 0.15)
            
                # Create rounded rectangle mask
                mask = Image.new('L', (art_size, art_size), 0)
                maskDraw = ImageDraw.Draw(mask)
                radius = 12  # Adjust corner radius
            
                # Draw rounded rectangle mask
                maskDraw.rectangle([radius, 0, art_size - radius, art_size], fill=255)
                maskDraw.rectangle([0, radius, art_size, art_size - radius], fill=255)
                maskDraw.pieslice([0, 0, radius * 2, radius * 2], 180, 270, fill=255)
                maskDraw.pieslice([art_size - radius * 2, 0, art_size, radius * 2], 270, 360, fill=255)
                maskDraw.pieslice([0, art_size - radius * 2, radius * 2, art_size], 90, 180, fill=255)
                maskDraw.pieslice([art_size - radius * 2, art_size - radius * 2, art_size, art_size], 0, 90, fill=255)
            
                # Resize and mask album art
                art = self.musicInfo['image'].resize((art_size, art_size), Image.Resampling.LANCZOS)
                art.putalpha(mask)
            
                # Center horizontally
                art_x = (width - art_size) // 2
                art_y = top_padding
                overlay.paste(art, (art_x, art_y), art)
            
                # Increase spacing between elements
                text_start_y = art_y + art_size + int(height * 0.08)  # padding below art
                spacing = int(height * 0.055)  # height for spacing between text elements
            
                title_y = text_start_y
                artist_y = title_y + spacing
                album_y = artist_y + spacing
            else:
                # If no album art, position text in center
                mid_height = height // 2
                spacing = int(height * 0.12)  # Larger spacing without album art
            
                title_y = mid_height - spacing
                artist_y = mid_height
                album_y = mid_height + spacing

            # Draw text with subtle gradient shadow
            shadow_offset = 2 # Slightly larger shadow for 640x640
            shadow_color = (0, 0, 0, 180)

            # Helper function for drawing text with shadow
            def draw_text_with_shadow(y_pos, text, font):
                # Draw shadow
                overlayCanvas.text(
                    (width // 2 + shadow_offset, y_pos + shadow_offset),
                    text=text[:35],  # Limit text length
                    anchor="mm",
                    font=font,
                    fill=shadow_color
                )
                # Draw main text
                overlayCanvas.text(
                    (width // 2, y_pos),
                    text=text[:35],
                    anchor="mm",
                    font=font,
                    fill=(255, 255, 255, alpha)
                )

            # Draw all text elements
            draw_text_with_shadow(title_y, self.musicInfo['title'], self.music_fonts['title'])
            draw_text_with_shadow(artist_y, self.musicInfo['artist'], self.music_fonts['artist'])
            draw_text_with_shadow(album_y, self.musicInfo['album'], self.music_fonts['album'])

            return overlay.rotate(data["rotation"])
        else:
            return overlay.rotate(data["rotation"])

    @timing
    def compose(self, data, img, overlay):
        if data["composition"] == "MIX":
            return Image.composite(
                img, Image.new("RGBA", img.size, (0, 0, 0, 0)), overlay
            )
    
        if data["composition"] == "OVERLAY":
            if overlay is not None:
                return Image.alpha_composite(img, overlay)
            else:
                return img

    @timing
    def addOverlay(self, postData, rawTime):
        startTime = time.time()

        data = json.loads(postData.decode("utf-8"))
        data["size"] = lcd.resolution
        img = self.parseImage(data)

        if data["composition"] != "OFF":
            overlay = self.renderOverlay(data)
            img = self.compose(data, img, overlay)

        overlayTime = time.time() - startTime

        self.frameBuffer.put(
            (
                lcd.imageToFrame(img, adaptive=data["colorPalette"] == "ADAPTIVE"),
                rawTime,
                overlayTime,
            )
        )
        if data.get("musicOverlay"):
            image_url = self.musicInfo.get('image')
            if image_url:
                image_base64 = download_image(image_url)
                if image_base64:
                    # Proceed with overlay using the downloaded image
                    pass
                else:
                    debug("Image could not be downloaded for overlay.")


class StatsProducer(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True

    def run(self):
        debug("CPU stats producer started")
        while True:
            stats["cpu"] = psutil.cpu_percent(1)


class Systray(Thread):
    def __init__(self):
        Thread.__init__(self)
        # monkey patching pystray to open menu on left click
        from pystray._util import win32

        win32.WM_LBUTTONUP = 0x0205
        win32.WM_RBUTTONUP = 0x0202

        self.menu = pystray.Menu(
            pystray.MenuItem("Device: " + lcd.name, self.noop, enabled=False),
            pystray.MenuItem(
                "Bridge: http://127.0.0.1:{}".format(PORT), self.noop, enabled=False
            ),
            pystray.MenuItem(
                "SignalRGBPlugin: "
                + ("installed" if pluginInstalled else "not installed"),
                self.noop,
                enabled=False,
            ),
            pystray.MenuItem(
                self.getFPS,
                self.noop,
                enabled=False,
            ),
            pystray.MenuItem("Exit", self.stop),
        )
        self.icon = pystray.Icon(
            name="KrakenLCDBridge",
            title="KrakenLCDBridge",
            icon=Image.open(APP_ICON).resize((64, 64)),
            menu=self.menu,
        )

    def run(self):
        debug("Systray icon started")
        self.icon.run()

    def getFPS(self, _):
        return "FPS: {:.2f}".format(frameWriterWithStats.fps.value)

    def noop(self):
        pass

    def stop(self):
        self.icon.stop()


class FrameWriterWithStats(FrameWriter):
    def __init__(self, frameBuffer: queue.Queue, lcd: driver.KrakenLCD):
        super().__init__(frameBuffer, lcd)
        self.updateAIOStats()

    def updateAIOStats(self):
        if time.time() - self.lastDataTime > 1:
            self.lastDataTime = time.time()
            stats.update(self.lcd.getStats())

    def onFrame(self):
        super().onFrame()
        self.updateAIOStats()
        # dynamically adjust gif color precisione (and size) base on how much 'free time' we have.

        # if freeTime > 5 and colors < 256:
        #     colors = min(256, round(colors * 1.05))
        # if freeTime < -2 and colors > 8:
        #     colors = max(MIN_COLORS, round(colors * 0.95))


dataBuffer = queue.Queue(maxsize=2)
frameBuffer = queue.Queue(maxsize=2)

rawProducer = RawProducer(dataBuffer)
overlayProducer = OverlayProducer(dataBuffer, frameBuffer)
frameWriterWithStats = FrameWriterWithStats(frameBuffer, lcd)
statsProducer = StatsProducer()
systray = Systray()


rawProducer.start()
overlayProducer.start()
frameWriterWithStats.start()
statsProducer.start()
systray.start()

print("SignalRGB Kraken bridge started")


try:
    while True:
        time.sleep(1)
        systray.icon.update_menu()
        if not (
            statsProducer.is_alive()
            and rawProducer.is_alive()
            and overlayProducer.is_alive()
            and frameWriterWithStats.is_alive()
            and systray.is_alive()
        ):
            raise KeyboardInterrupt("Some thread is dead")
except KeyboardInterrupt:
    frameWriterWithStats.shouldStop = True
    frameWriterWithStats.join()
    systray.stop()
