# ~~ IMPORT LIBRARIES ~~
# Standard modules
import datetime
import json
import logging
import socket
import time
import traceback
from io import BytesIO
from importlib import resources
from ipaddress import IPv4Address
from os import environ
from socket import gethostname

# External modules
import fontawesomefree
import magic
import nmcli
from cairosvg import svg2png
from PIL.ImageFont import FreeTypeFont
from font_fredoka_one import FredokaOne
from inky import auto
from inky.eeprom import read_eeprom
from inky.mock import InkyMockPHAT, InkyMockPHATSSD1608, InkyMockWHAT, InkyMockImpression
from PIL import Image, ImageFont, ImageDraw
import paho.mqtt.client as mqtt
from rich import print as rprint
from rich.logging import RichHandler

# We're not controlling everything, this package doesn't need root.
# nmcli.disable_use_sudo()

# ~~ INIT LOGGING ~~
FORMAT = "%(message)s"
logging.basicConfig(
    level="DEBUG", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(markup=True, rich_tracebacks=True)]
)
log = logging.getLogger("rich")

# ~~ GET IP ADDRESS AND HOSTNAME ~~
ip_address = IPv4Address(nmcli.connection.show(nmcli.connection()[0].name)['IP4.ADDRESS[1]'].split('/')[0])
hostname = gethostname()
log.info(f"My IP address is {ip_address}")
log.info(f"My hostname is {hostname}")

# ~~ INIT INKY DISPLAY ~~
try:
    display = auto() # Identifies the Inky display meaning this code should work on more than just the pHAT
    display_type = read_eeprom(None).get_variant()
except RuntimeError:
    display = InkyMockPHAT('red') # Simulate a Red/White/Black Inky pHAT
    display_type = "phat"

max_items = display.HEIGHT // 45

log.info(f"I am using a {display.colour} Inky {display_type}, my dimensions are {display.WIDTH}x{display.HEIGHT}. I can fit {max_items} items.")

# ~~ DEFINE COLOURS ~~
BLACK = display.BLACK
WHITE = display.WHITE
COLOUR = (display.colour == 'red' and display.RED) or \
         (display.colour == 'yellow' and display.YELLOW) or \
         (display.colour == 'multi' and display.RED) or \
         BLACK
COLOUR_FG = (display.colour == 'red' and WHITE) or \
            (display.colour == 'yellow' and BLACK) or \
            (display.colour == 'multi' and display.WHITE) or \
            WHITE # This being the colour that goes on top of `COLOR`

BLACK = display.BLACK
WHITE = display.WHITE
GREEN = (display.colour == 'multi' and display.GREEN) or COLOUR
BLUE = (display.colour == 'multi' and display.BLUE) or COLOUR
RED = display.RED
YELLOW = (display.colour == 'multi' and display.YELLOW) or WHITE
ORANGE = (display.colour == 'multi' and display.ORANGE) or COLOUR

# ~~ SET UP FONTS ~~
font = ImageFont.truetype('./fonts/IBMPlexSans-Bold.ttf', 24)
font_condensed = ImageFont.truetype('./fonts/IBMPlexSansCondensed-Bold.ttf', 24)
font_small = ImageFont.truetype('./fonts/IBMPlexSans-Bold.ttf', 18)
font_small_condensed = ImageFont.truetype('./fonts/IBMPlexSansCondensed-Bold.ttf', 18)
font_smaller = ImageFont.truetype('./fonts/IBMPlexSans-Regular.ttf', 14)
font_smaller_condensed = ImageFont.truetype('./fonts/IBMPlexSansCondensed-Regular.ttf', 14)

# ~~ IMAGE DRAWING STUFF ~~
def new_img():
    img = Image.new("P", (display.WIDTH, display.HEIGHT))
    return img, ImageDraw.Draw(img)

def get_font_awesome_icon(icon="circle-question"):
    icon_traversal = resources.files(fontawesomefree) / 'static' / 'fontawesomefree' / 'svgs' / 'solid' / (icon + '.svg')

    with icon_traversal.open("r") as f:
        svg = svg2png(file_obj=f)
        # print(svg)
        return Image.open(BytesIO(svg))

def get_var_name(var):
    for name, value in locals().items():
        if value is var:
            return name

def draw_icon(img, icon = "circle-question", x=0, y=0, w=0, h=0, colour=WHITE):
    if w == 0:
        w = h
    if h == 0:
        h = w
    x, y, w, h = int(x), int(y), int(w), int(h)

    icon = get_font_awesome_icon(icon)
    icon.thumbnail((w, h))
    padded_icon = Image.new("RGBA", (w, h))
    padded_icon.paste(icon, (int((w-icon.width)/2), int((h-icon.height)/2)))
    p_icon = Image.new("P", (w, h))
    # log.debug((icon.width, p_icon.width))
    p_draw = ImageDraw.Draw(p_icon)
    p_draw.rectangle([(0, 0), (w, h)], colour)
    img.paste(p_icon, (x, y), mask=padded_icon)
    # p_icon.show()
    # icon.show()

def get_wrapped_text(text: str, font: FreeTypeFont,
                         line_length: int):
        lines = ['']
        for word in text.split():
            line = f'{lines[-1]} {word}'.strip()
            if font.getlength(line) <= line_length:
                lines[-1] = line
            else:
                lines.append(word)
        return '\n'.join(lines)

def draw_text(text, draw, x=0, y=0, font_to_use: FreeTypeFont = font, colour=BLACK, align="left", baseline="top", wrap_px = 0, no_wrap=False):
    if wrap_px >= 1 and not no_wrap:
        text = get_wrapped_text(text, font_to_use, wrap_px)

    lines = text.splitlines()
    number_of_lines = len(lines)

    _, _, bounding_w, bounding_h = draw.multiline_textbbox((0, 0), text, font=font_to_use, spacing=0)
    if no_wrap and bounding_w >= wrap_px and not get_var_name(font_to_use).endswith("_condensed"):
        font_to_use = globals().get(get_var_name(font_to_use) + "_condensed", font_to_use)
        _, _, bounding_w, bounding_h = draw.multiline_textbbox((0, 0), text, font=font_to_use, spacing=0)

    if align == "right":
        x = x - bounding_w
    elif align == "center":
        x = x - (bounding_w / 2)

    if baseline == "bottom":
        y = y - bounding_h
    elif baseline == "middle":
        y = y - (bounding_h / 2)

    # draw.rectangle([(x, y), (x+bounding_w, y+bounding_h)], colour)

    log.debug("Drawing text [dim]\"%s\"[/dim] to (%s,%s).", text, x, y)
    # log.debug("Bounding: (%s,%s)", bounding_w, bounding_h)

    draw.multiline_text((x, y), text, font=font_to_use, fill=colour, spacing=0)

    # for l in range(len(lines)):
    #     line = lines[l]
    #     log.debug("Drawing line \"%s\", index %s, %s,%s", line, l, x, y + (l * font.size))
    #     # draw.rectangle([(x, y), (x+10, y+10)], colour)
    #     draw.text((x, y + (l * (font.size - bounding_y))), line, colour, font)


def draw_splash(subtitle="", colour=WHITE):
    log.info("[bold]Drawing splash screen[/bold]")
    log.debug(f"SPLASH SUBTITLE: {subtitle}")
    # log.debug(f"SPLASH BKG COLOUR: {colour}")

    display.set_border(colour)

    img, draw = new_img()
    header_colour = COLOUR
    text_colour = BLACK
    if colour == COLOUR:
        header_colour = COLOUR_FG
        text_colour = COLOUR_FG
    # log.debug(f"HEADER COLOUR: {header_colour}")
    # log.debug(f"TEXT COLOUR: {text_colour}")

    # Fill the image with the background colour
    draw.rectangle([(0, 0), (display.WIDTH, display.HEIGHT)], fill=colour)

    # Draw text
    draw_text("Thor", draw, 10, 10, colour=header_colour)
    draw_text(subtitle, draw, 10, int(15+font.size), colour=text_colour, font_to_use=font_smaller)
    draw_text(
        "Updated " + datetime.datetime.now().strftime("%H:%M"), draw,
        10, display.HEIGHT - 10, colour=text_colour,
        font_to_use=font_smaller, baseline="bottom")

    display.set_image(img)
    display.show()

class BodyStackItem:
    def __init__(self):
        self.icon = None
        self.headline = ""
        self.bg_colour = WHITE
        self.fg_colour = BLACK
        self.nowrap = False
        self.font = font_small
        self.subtitle = None

    def draw(self, img: Image, draw: ImageDraw, x=0, y=display.HEIGHT/2, w=display.WIDTH, h=display.HEIGHT/2):
        draw.rectangle([(x, y), (x+w, y+h)], self.bg_colour)

        text_offset_x = 15
        text_offset_y = 0
        if self.icon:
            text_offset_x += font.size
        if self.subtitle:
            text_offset_y = font.size / 3

        if self.icon:
            draw_icon(img, self.icon, x + 10, y + (h / 2) - 10, font.size, colour=self.fg_colour)

        wrap_px = display.width-text_offset_x-x

        draw_text(self.headline, draw, x + text_offset_x, y + (h / 2) - text_offset_y, font_to_use=self.font, baseline="middle", colour=self.fg_colour, wrap_px=wrap_px, no_wrap=self.nowrap)
        if self.subtitle: draw_text(self.subtitle, draw, x + text_offset_x, y + (h / 2) + text_offset_y, font_to_use=font_smaller, baseline="middle", colour=self.fg_colour, wrap_px=wrap_px, no_wrap=self.nowrap)

class EPaperImage:
    def __init__(self):
        self.img, self.draw = new_img()
        self.header_compact = False
        self.header_headline = None
        self.header_icon = None

        self.body_items = []

        self.timestamp = time.time()
        self.temperature = None

    def draw_header(self, bg_colour=BLACK, fg_colour=WHITE):
        height = (self.header_compact and 18) or (display.HEIGHT / 2)
        header_font = (self.header_compact and font_smaller) or font
        self.draw.rectangle([(0, 0), (display.WIDTH, height)], bg_colour)

        # Draw the icon
        if self.header_icon:
            # log.debug(self.header_icon)
            draw_icon(self.img, icon=self.header_icon, x=10, y=(height/2)-header_font.size/2, w=int(header_font.size))

        # Draw the headline
        if self.header_headline:
            if self.header_icon: x = int(15 + header_font.size)
            else: x = 15
            draw_text(self.header_headline, self.draw, x, height/2, header_font, fg_colour, baseline="middle",
                      wrap_px=display.width-x, no_wrap=False)

        # Draw the box behind update time
        update_time = datetime.datetime.fromtimestamp(self.timestamp)
        update_time_string = update_time.strftime("%H:%M")
        temperature_string = f"{self.temperature}ºC"
        _, _, temp_width, _ = font_smaller.getbbox(temperature_string)
        _, _, time_width, _ = font_smaller.getbbox(update_time_string)
        if self.header_compact:
            box_width = display.WIDTH - 20 - time_width - temp_width
        else:
            box_width = display.WIDTH - 20 - max(time_width, temp_width)
        self.draw.rectangle([(box_width, 0), (display.WIDTH, height)], bg_colour)

        temperature_location = display.WIDTH - 10
        time_temperature_y_offset = (font_small.size / 2)
        if self.header_compact:
            temperature_location = display.WIDTH - 15 - time_width
            time_temperature_y_offset = 0

        # Draw the temperature
        if self.temperature:
            draw_text(temperature_string, self.draw, temperature_location, (height / 2) - time_temperature_y_offset, font_to_use=font_smaller, colour=fg_colour,
                      align="right", baseline="middle")

        # Draw the update time
        draw_text(update_time_string, self.draw, display.WIDTH - 10, (height / 2) + time_temperature_y_offset,
                  colour=fg_colour, font_to_use=font_smaller,
                  align="right", baseline="middle")

    def draw_body(self):
        if self.header_compact: start_y = 18
        else: start_y = display.HEIGHT/2

        # log.debug(self.body_items)

        if not self.body_items:
            log.debug("No items to draw")
            return

        offset_y = start_y
        item_height = (display.HEIGHT - start_y) / min(max(len(self.body_items), 1), max_items)
        log.debug('Item height: %s px', item_height)

        for i in range(len(self.body_items)):
            if i >= max_items: break
            item = self.body_items[i - 1]
            if self.header_compact: item.font = font_small
            log.debug("Drawing %s", item.__dict__)
            item.draw(self.img, self.draw, x=0, y=offset_y, w=display.WIDTH, h=item_height)
            offset_y += item_height


    def show_image(self, border=None):
        display.set_image(self.img)
        if border:
            display.set_border(border)
        display.show()


# Show the initial splash page
draw_splash(f"Hi! I'm {ip_address}\nWaiting for connection...")

# Initialise variables
alerts = []
weather = {}

# ~~ MQTT THINGS ~~
def mqtt_on_connect(client, userdata, flags, reason_code, properties):
    log.info('Connected to MQTT broker. Reason code: ' + str(reason_code))
    if reason_code != "Success":
        raise ConnectionRefusedError(reason_code)

    client.subscribe('thor/alerts')
    client.subscribe('thor/weather')
    # ask for weather data
    client.publish("thor/ask", "Looking for data.", qos=1)

def mqtt_on_message(client, userdata, msg):
    global alerts, weather
    log.info(f"Recieved message. Topic: {msg.topic}")
    content = BytesIO(msg.payload)
    content_snippet = content.read(2048)
    content.seek(0)
    payload_mime_type = magic.from_buffer(content_snippet, mime=True)

    img = EPaperImage()
    severe = False

    if payload_mime_type.endswith("/json"):
        content = json.loads(content.read().decode('utf8'))
        if "icon" in content and not ("alert_type" in content):
            img.header_icon = content.get('icon', None)
        log.debug(f"Message content: {content}")
        if "timestamp" in content:
            img.timestamp = content.get('timestamp', time.time())
        if msg.topic == "thor/weather":
            alerts = content.get("alerts", [])
            if "weather" in content:
                weather = content.get('weather')
                weather['icon'] = img.header_icon
        if msg.topic == "thor/alerts":
            alerts.append(content)

    img.temperature = weather.get("temperature", 0.0)
    img.header_headline = weather.get("headline", "Unknown")
    if not img.header_icon: img.header_icon = weather.get("icon", None)

    alerts.sort(key=lambda d: d['timestamp'], reverse=True)

    for alert in alerts:
        body_item = BodyStackItem()
        if alert.get('severity', 0) == 2:
            severe = True
            body_item.fg_colour = COLOUR_FG
            body_item.bg_colour = ORANGE
        elif alert.get('severity', 0) == 1:
            body_item.fg_colour = BLACK
            body_item.bg_colour = YELLOW
        body_item.icon = alert.get('icon', None)
        body_item.headline = alert.get('headline')
        body_item.subtitle = alert.get('subtitle')
        body_item.nowrap = alert.get('nowrap', False)
        img.body_items.append(body_item)

    # body_item = BodyStackItem()
    # body_item.bg_colour = COLOUR
    # body_item.fg_colour = COLOUR_FG
    # body_item.icon = "triangle-exclamation"
    # body_item.headline = "Orange Wind Warning"
    # img.body_items.append(body_item)

    if len(img.body_items) >= 2:
        img.header_compact = True
    elif len(img.body_items) <= 0:
        body_item = BodyStackItem()
        body_item.fg_colour = BLACK
        body_item.bg_colour = WHITE
        body_item.icon = "circle-check"
        body_item.headline = "All clear :)"
        body_item.subtitle = "No alerts today."
        img.body_items.append(body_item)

    img.draw_body()
    if severe:
        img.draw_header(bg_colour=COLOUR, fg_colour=COLOUR_FG)
        img.show_image(COLOUR)
    else:
        img.draw_header()
        img.show_image(BLACK)


# ~~ INITIALISE MQTT ~~
try:
    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqttc.on_connect = mqtt_on_connect
    mqttc.on_message = mqtt_on_message

    mqttc.username_pw_set(username='thor', password='s9xQMrOGDBWX0')
    mqttc.connect(environ.get('MQTT_BROKER', 'triangulum.local'), 1883, 60)
    mqttc.loop_forever()
except (socket.gaierror, ConnectionRefusedError, TimeoutError, OSError) as error:
    draw_splash(f"Connection failed!\n{error}", COLOUR)
    log.exception(str(error))
except Exception as error:
    draw_splash(f"{error}", COLOUR)
    log.exception(str(error))

# while True:
#     pass
# time.sleep(5)
