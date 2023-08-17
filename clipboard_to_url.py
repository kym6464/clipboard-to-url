import sys
import pyperclip
import hashlib
import io
import mimetypes
import os

from PIL import Image, UnidentifiedImageError
from PIL.Image import Image as PILImage
from PIL import ImageGrab
from pillow_heif import register_heif_opener
from pathlib import Path
from dotenv import dotenv_values
from google.cloud import storage


PROJECT_ID: str
BUCKET_ID: str
JPEG_QUALITY: int

register_heif_opener()


def extension_to_type(extension: str) -> str:
    assert isinstance(extension, str), f"Expected extension to be str, received: {extension}"
    content_type = mimetypes.types_map.get(extension)
    assert content_type, f"Failed to get content_type for {extension=}"
    return content_type


def image_to_bytes(im: PILImage) -> bytes:
    im_prep = im.convert('RGB')
    with io.BytesIO() as buffer:
        im_prep.save(buffer, format="JPEG", jpeg_quality=JPEG_QUALITY)
        return buffer.getvalue()


def hash_bytes(value: bytes) -> str:
    hasher = hashlib.md5()
    hasher.update(value)
    return hasher.hexdigest()


def prepare_image(image: PILImage) -> tuple[bytes, str]:
    content = image_to_bytes(image)
    content_hash = hash_bytes(content)
    blob_name = f"{content_hash}.jpg"
    return content, blob_name


def read_from_path(path: Path) -> tuple[bytes, str]:
    assert os.access(str(path), os.R_OK), f"Permission error"
    assert path.exists() and path.is_file()

    try:
        with Image.open(path) as image:
            return prepare_image(image)
    except UnidentifiedImageError:
        pass

    content = path.read_bytes()
    content_hash = hash_bytes(content)
    blob_name = f"{content_hash}{path.suffix}"
    return content, blob_name


def upload_blob(content, blob_name):
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_ID)
    blob = bucket.blob(blob_name)

    kwds = {}
    try:
        kwds["content_type"] = extension_to_type(Path(blob_name).suffix)
    except Exception:
        pass

    blob.upload_from_string(content, **kwds)
    return blob.public_url


def read_config(env_file: Path):
    global PROJECT_ID, BUCKET_ID, JPEG_QUALITY

    assert env_file.exists(), f"Missing file {env_file}"
    config = dotenv_values(env_file)

    PROJECT_ID = config.get("PROJECT_ID")
    assert PROJECT_ID, f"Missing PROJECT_ID in {env_file}"

    BUCKET_ID = config.get("BUCKET_ID")
    assert BUCKET_ID, f"Missing BUCKET_ID in {env_file}"

    JPEG_QUALITY = config.get("JPEG_QUALITY")
    assert JPEG_QUALITY, f"Missing JPEG_QUALITY in {env_file}"
    try:
        JPEG_QUALITY = int(JPEG_QUALITY)
    except ValueError:
        raise TypeError(f"Expected JPEG_QUALITY to be an integer, received {JPEG_QUALITY}")


if __name__ == "__main__":
    env_file = Path(__file__).parent.joinpath(".env").resolve()
    try:
        read_config(env_file)
    except Exception as e:
        print(f"Failed to read config: {e}")
        sys.exit()

    image: PILImage | None = None
    try:
        value = ImageGrab.grabclipboard()
        if isinstance(value, PILImage):
            image = value
    except Exception as e:
        pass

    content: bytes | None = None
    blob_name: str | None = None
    if image is not None:
        content, blob_name = prepare_image(image)
    elif value := pyperclip.paste():        
        try:
            content, blob_name = read_from_path(Path(value.strip()))
        except Exception:
            pass
    
    if content is None:
        print("Nothing to upload")
        sys.exit()

    url = upload_blob(content, blob_name)
    pyperclip.copy(url)
