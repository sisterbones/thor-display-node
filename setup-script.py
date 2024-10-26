
# ~~ IMPORT LIBRARIES ~~
# External dependencies
from font_fredoka_one import FredokaOne
from inky.mock import InkyMockPHAT, InkyMockWHAT
from inky import auto
from PIL import Image, ImageFont, ImageDraw
import qrcode
from qrcode.image.styledpil import StyledPilImage

qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=3,
    border=5,
    image_factory=StyledPilImage
)

qr.add_data('WIFI:T:nopass;S:Bridge;H:false')
qr.make()

display = InkyMockPHAT("red")

display.set_border(display.WHITE)
img = Image.new("P", (display.WIDTH, display.HEIGHT))
draw = ImageDraw.Draw(img)

font = ImageFont.truetype(FredokaOne, 22)
font_small = ImageFont.truetype(FredokaOne, 16)


qr_img = qr.make_image().quantize(colors=2)

img.paste(qr_img, (display.WIDTH - qr_img.width, 0))

display.set_image(img)
display.show()

while True:
    pass
