import base64
import secrets
from io import BytesIO

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from .models import CaptchaChallenge


CAPTCHA_CHARACTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _random_between(minimum, maximum):
    return minimum + secrets.randbelow(maximum - minimum + 1)


def generate_captcha_answer():
    return "".join(secrets.choice(CAPTCHA_CHARACTERS) for _ in range(settings.CAPTCHA_LENGTH))


def _captcha_font(size=42):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def render_captcha_png(answer):
    width, height = 240, 84
    image = Image.new(
        "RGB",
        (width, height),
        (_random_between(235, 255), _random_between(235, 255), _random_between(235, 255)),
    )
    draw = ImageDraw.Draw(image)

    for _ in range(7):
        draw.line(
            (
                _random_between(0, width),
                _random_between(0, height),
                _random_between(0, width),
                _random_between(0, height),
            ),
            fill=(_random_between(90, 190), _random_between(90, 190), _random_between(90, 190)),
            width=_random_between(1, 3),
        )

    font = _captcha_font()
    character_width = width // (len(answer) + 1)
    for index, character in enumerate(answer):
        glyph = Image.new("RGBA", (56, 68), (255, 255, 255, 0))
        glyph_draw = ImageDraw.Draw(glyph)
        glyph_draw.text(
            (7, 5),
            character,
            font=font,
            fill=(_random_between(15, 90), _random_between(15, 90), _random_between(15, 90), 255),
        )
        glyph = glyph.rotate(_random_between(-18, 18), resample=Image.Resampling.BICUBIC, expand=True)
        x = 9 + index * character_width + _random_between(-2, 3)
        y = _random_between(3, 15)
        image.paste(glyph, (x, y), glyph)

    draw = ImageDraw.Draw(image)
    for _ in range(180):
        x = _random_between(0, width - 1)
        y = _random_between(0, height - 1)
        draw.point(
            (x, y),
            fill=(_random_between(80, 210), _random_between(80, 210), _random_between(80, 210)),
        )

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def create_login_captcha():
    answer = generate_captcha_answer()
    challenge = CaptchaChallenge(
        purpose=CaptchaChallenge.Purpose.LOGIN_OTP,
        expires_at=CaptchaChallenge.expiry_from_now(),
        max_attempts=settings.CAPTCHA_MAX_ATTEMPTS,
    )
    challenge.set_answer(answer)
    image_data = render_captcha_png(answer)
    challenge.save()
    encoded_image = base64.b64encode(image_data).decode("ascii")
    return challenge, f"data:image/png;base64,{encoded_image}"


def consume_login_captcha(challenge_id, answer):
    with transaction.atomic():
        try:
            challenge = CaptchaChallenge.objects.select_for_update().get(
                pk=challenge_id,
                purpose=CaptchaChallenge.Purpose.LOGIN_OTP,
            )
        except CaptchaChallenge.DoesNotExist:
            return False

        if not challenge.can_attempt:
            return False

        if not challenge.check_answer(answer):
            challenge.attempt_count += 1
            challenge.save(update_fields=["attempt_count"])
            return False

        challenge.used_at = timezone.now()
        challenge.save(update_fields=["used_at"])
        return True
