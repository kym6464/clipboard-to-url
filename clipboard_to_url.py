import sys
import pyperclip
import hashlib
import io
import mimetypes
import os

from PIL import Image, UnidentifiedImageError
from PIL.Image import Image as PILImage
from PIL import ImageGrab
from pathlib import Path
from dotenv import dotenv_values
from google.cloud import storage


def extension_to_type(extension: str) -> str:
    assert isinstance(extension, str), f"Expected extension to be str, received: {extension}"
    content_type = mimetypes.types_map.get(extension)
    assert content_type, f"Failed to get content_type for {extension=}"
    return content_type


def image_to_bytes(im: PILImage) -> bytes:
    im_prep = im.convert('RGB')
    with io.BytesIO() as buffer:
        im_prep.save(buffer, format="JPEG", jpeg_quality=jpeg_quality)
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
        with Image.open(path, formats=["JPEG", "PNG"]) as image:
            return prepare_image(image)
    except UnidentifiedImageError:
        pass

    content = path.read_bytes()
    content_hash = hash_bytes(content)
    blob_name = f"{content_hash}{path.suffix}"
    return content, blob_name


def upload_blob(content, blob_name):
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_id)
    blob = bucket.blob(blob_name)
    content_type = extension_to_type(Path(blob_name).suffix)
    blob.upload_from_string(content, content_type=content_type)
    return blob.public_url


if __name__ == "__main__":
    env_file = Path(__file__).parent.joinpath(".env").resolve()
    if not env_file.exists():
        print(f"Missing file {env_file}")
        sys.exit()

    config = dotenv_values(env_file)

    project_id = config.get("PROJECT_ID")
    if not project_id:
        print(f"Missing PROJECT_ID in {env_file}")
        sys.exit()

    bucket_id = config.get("BUCKET_ID")
    if not bucket_id:
        print(f"Missing BUCKET_ID in {env_file}")
        sys.exit()

    jpeg_quality = config.get("JPEG_QUALITY")
    if not jpeg_quality:
        print(f"Missing JPEG_QUALITY in {env_file}")
        sys.exit()
    try:
        jpeg_quality = int(jpeg_quality)
    except ValueError:
        print(f"Expected JPEG_QUALITY to be an integer, received {jpeg_quality}")
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
    
    if content is None and (value := pyperclip.paste()):        
        try:
            content, blob_name = read_from_path(Path(value.strip()))
        except Exception:
            pass
    
    if content is None:
        print("Nothing to upload")
        sys.exit()

    url = upload_blob(content, blob_name)
    pyperclip.copy(url)
