import sys
import pyperclip
import hashlib
import io
import mimetypes
import os
import json
import argparse
import re

from PIL import Image, UnidentifiedImageError
from PIL.Image import Image as PILImage
from PIL import ImageGrab
from pillow_heif import register_heif_opener
from pathlib import Path
from dotenv import dotenv_values
from google.cloud import storage
from compact_json import Formatter, EolStyle


PROJECT_ID: str
BUCKET_ID: str
OBJECT_PREFIX: str | None
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


def read_json(value: str) -> tuple[bytes, str]:
    json_data = json.loads(value)
    assert json_data, "Expected non-empty JSON object or array"

    formatter = Formatter()
    formatter.indent_spaces = 2
    formatter.max_inline_complexity = 10
    formatter.json_eol_style = EolStyle.LF
    json_string = formatter.serialize(json_data)

    content = json_string.encode()
    blob_name = f"{hash_bytes(content)}.json"

    return content, blob_name

def read_csv(value: str) -> tuple[bytes, str] | None:
    lines = value.strip().splitlines()
    assert len(lines) > 0, "Expected non-empty CSV string"
    assert ',' in lines[0] or ';' in lines[0] or '\t' in lines[0], "Expected comma, semicolon, or tab delimiter in header"
    content = value.encode()
    blob_name = f"{hash_bytes(content)}.csv"
    return content, blob_name

def read_sql(value: str) -> tuple[bytes, str] | None:
    sql_keywords = ["SELECT", "FROM", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "JOIN", "WHERE", "GROUP BY", "ORDER BY"]
    pattern = r'\b(' + '|'.join(sql_keywords) + r')\b'
    assert re.search(pattern, value, re.IGNORECASE), "Expected SQL query"
    content = value.encode()
    blob_name = f"{hash_bytes(content)}.sql"
    return content, blob_name

def read_file(path: Path) -> tuple[bytes, str]:
    assert os.access(str(path), os.R_OK), f"Permission error"
    assert path.exists() and path.is_file()

    try:
        with Image.open(path) as image:
            return prepare_image(image)
    except UnidentifiedImageError:
        pass

    try:
        return read_json(path.read_text())
    except Exception:
        pass

    try:
        return read_csv(path.read_text())
    except Exception:
        pass

    try:
        return read_sql(path.read_text())
    except Exception:
        pass


    content = path.read_bytes()
    content_hash = hash_bytes(content)
    blob_name = f"{content_hash}{path.suffix}"
    return content, blob_name


def upload_blob(content, blob_name):
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_ID)

    if OBJECT_PREFIX:
        blob_name = OBJECT_PREFIX + blob_name
    blob = bucket.blob(blob_name)

    if blob.exists():
        return {
            "public_url": blob.public_url,
            "gcs_uri": f"gs://{BUCKET_ID}/{blob_name}"
        }

    kwds = {}
    try:
        kwds["content_type"] = extension_to_type(Path(blob_name).suffix)
    except Exception:
        pass

    blob.upload_from_string(content, **kwds)
    return {
        "public_url": blob.public_url,
        "gcs_uri": f"gs://{BUCKET_ID}/{blob_name}"
    }


def get_blob_to_upload() -> tuple[bytes, str] | None:
    try:
        image = ImageGrab.grabclipboard()
        if isinstance(image, PILImage):
            return prepare_image(image)
    except Exception:
        pass

    value = pyperclip.paste()
    if not value:
        return

    try:
        return read_file(Path(value.strip()))
    except Exception:
        pass

    try:
        return read_json(value)
    except Exception:
        pass

    try:
        return read_csv(value)
    except Exception:
        pass

    try:
        return read_sql(value)
    except Exception:
        pass

def read_config(env_file: Path):
    global PROJECT_ID, BUCKET_ID, OBJECT_PREFIX, JPEG_QUALITY

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

    OBJECT_PREFIX = config.get("OBJECT_PREFIX")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Upload content from clipboard or file to Google Cloud Storage.')
    parser.add_argument('-o', '--output', choices=['clipboard', 'stdout'], default='clipboard',
                        help='Specify where to output the resulting URL (default: clipboard)')
    args = parser.parse_args()

    env_file = Path(__file__).parent.joinpath(".env").resolve()
    try:
        read_config(env_file)
    except Exception as e:
        print(f"Failed to read config: {e}")
        sys.exit(1)

    to_upload = get_blob_to_upload()
    if to_upload is None:
        print("Nothing to upload")
        sys.exit()

    content, blob_name = to_upload
    result = upload_blob(content, blob_name)

    if args.output == 'clipboard':
        pyperclip.copy(result["public_url"])
    else:
        print(json.dumps(result))
