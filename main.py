# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "compact-json==1.5.2",
#     "google-cloud-storage==2.10.0",
#     "markdown-it-py[linkify]==4.0.0",
#     "pillow==11.3.0",
#     "pillow-heif==1.1.0",
#     "pyperclip==1.8.2",
#     "python-dotenv==1.0.0",
# ]
# ///
import sys
import re
import pyperclip
import hashlib
import io
import mimetypes
import os
import json
import argparse

from PIL import Image, UnidentifiedImageError
from PIL.Image import Image as PILImage
from PIL import ImageGrab
from pillow_heif import register_heif_opener
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import storage
from compact_json import Formatter, EolStyle


PROJECT_ID: str
BUCKET_ID: str
OBJECT_PREFIX: str | None
JPEG_QUALITY: int
URL_TEMPLATE: str | None

register_heif_opener()


def remove_surrounding_quotes(s):
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def unescape_shell_path(path: str) -> str:
    """Convert shell-escaped path to actual file path.
    
    Handles common shell escapes like:
    - \\  (escaped space) -> space
    - \\' (escaped single quote) -> '
    - \\" (escaped double quote) -> "
    """
    return path.replace(r'\ ', ' ').replace(r"\'", "'").replace(r'\"', '"')


def extension_to_type(extension: str) -> str:
    assert isinstance(extension, str), f"Expected extension to be str, received: {extension}"

    content_type = mimetypes.types_map.get(extension)
    assert content_type, f"Failed to get content_type for {extension=}"

    # Add charset for text-based formats to ensure proper UTF-8 rendering
    if extension in ('.txt', '.json', '.csv', '.html', '.md'):
        content_type += '; charset=utf-8'

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

def read_csv(value: str) -> tuple[bytes, str]:
    lines = value.strip().splitlines()
    assert len(lines) >= 2, "Expected at least 2 lines for CSV structure"
    
    # Detect delimiter from first line
    delimiter = None
    for delim in [',', ';', '\t']:
        if delim in lines[0]:
            delimiter = delim
            break
    assert delimiter, "Expected comma, semicolon, or tab delimiter in header"
    
    # Validate structure: check that multiple lines have consistent field counts
    field_counts = []
    for line in lines[:min(5, len(lines))]:
        if not line.strip():
            continue
        field_count = line.count(delimiter) + 1
        field_counts.append(field_count)
    
    # Require at least 2 lines with data and consistent field counts
    assert len(field_counts) >= 2, "Expected at least 2 non-empty lines"
    assert len(set(field_counts)) == 1, "Expected consistent field counts across lines"
    assert field_counts[0] >= 2, "Expected at least 2 fields per line"
    
    content = value.encode()
    blob_name = f"{hash_bytes(content)}.csv"
    return content, blob_name

def read_html(value: str) -> tuple[bytes, str]:
    content = value.encode()
    blob_name = f"{hash_bytes(content)}.html"
    return content, blob_name

def read_markdown(value: str, sidecars: list | None = None) -> tuple[bytes, str]:
    from markdown_it import MarkdownIt

    md = MarkdownIt("gfm-like")
    rendered_html = md.render(value)

    html_document = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }}
        img {{ max-width: 100%; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        code {{ background-color: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
        pre {{ background-color: #f4f4f4; padding: 1rem; border-radius: 5px; overflow-x: auto; }}
        pre code {{ background-color: transparent; padding: 0; }}
        blockquote {{ border-left: 4px solid #ddd; margin: 0; padding-left: 1rem; color: #666; }}
    </style>
</head>
<body>
{rendered_html}
</body>
</html>"""

    content = html_document.encode()
    md_hash = hash_bytes(value.encode())
    blob_name = f"{md_hash}.html"

    if sidecars is not None:
        sidecars.append((value.encode(), f"{md_hash}.md", "text/markdown; charset=utf-8"))

    return content, blob_name

def read_text(value: str, min_length: int = 10) -> tuple[bytes, str]:
    trimmed_value = value.strip()
    assert trimmed_value, "Expected non-empty string after trimming whitespace"
    assert len(trimmed_value) >= min_length, f"Expected string to be at least {min_length} characters long"

    content = value.encode()
    blob_name = f"{hash_bytes(content)}.txt"
    return content, blob_name

def process_text(value: str, content_type: str, sidecars: list | None = None, min_length: int = 10) -> tuple[bytes, str]:
    base_type = content_type.split(';')[0].strip()
    if base_type == 'text/markdown':
        return read_markdown(value, sidecars)
    if base_type == 'text/csv':
        return read_csv(value)
    if base_type == 'text/html':
        return read_html(value)
    if base_type == 'application/json':
        return read_json(value)
    return read_text(value, min_length=min_length)

def read_file(path_str: str, content_type: str = None, raw_markdown: bool = False, sidecars: list | None = None) -> tuple[bytes, str, str]:
    path_str = remove_surrounding_quotes(path_str)
    path_str = unescape_shell_path(path_str)
    assert os.access(path_str, os.R_OK), f"Permission error"

    path = Path(path_str)
    assert path.exists() and path.is_file()

    original_filename = path.name
    suffix = path.suffix.lower()

    if content_type:
        base_type = content_type.split(';')[0].strip()
        if base_type.startswith('image/'):
            with Image.open(path) as image:
                content, blob_name = prepare_image(image)
                return content, blob_name, original_filename
        if base_type.startswith('text/') or base_type == 'application/json':
            content, blob_name = process_text(path.read_text(), content_type, sidecars)
            return content, blob_name, original_filename
        # Binary content type (e.g. application/zip): upload raw bytes
        content = path.read_bytes()
        blob_name = f"{hash_bytes(content)}{suffix}"
        return content, blob_name, original_filename

    # Recognized image suffix: direct dispatch
    if mimetypes.types_map.get(suffix, '').startswith('image/'):
        try:
            with Image.open(path) as image:
                if image.format != 'GIF':
                    content, blob_name = prepare_image(image)
                    return content, blob_name, original_filename
        except UnidentifiedImageError:
            pass
        # GIF or unidentified: upload as raw bytes
        content = path.read_bytes()
        blob_name = f"{hash_bytes(content)}{suffix}"
        return content, blob_name, original_filename

    if suffix == '.json':
        content, blob_name = read_json(path.read_text())
        return content, blob_name, original_filename

    if suffix == '.csv':
        content, blob_name = read_csv(path.read_text())
        return content, blob_name, original_filename

    if suffix == '.html':
        content, blob_name = read_html(path.read_text())
        return content, blob_name, original_filename

    if suffix == '.md' and not raw_markdown:
        content, blob_name = read_markdown(path.read_text(), sidecars)
        return content, blob_name, original_filename

    if suffix == '.txt':
        content, blob_name = read_text(path.read_text())
        return content, blob_name, original_filename

    # Unrecognized suffix (or .md with --raw-markdown): content sniffing waterfall
    try:
        with Image.open(path) as image:
            if image.format != 'GIF':
                content, blob_name = prepare_image(image)
                return content, blob_name, original_filename
    except Exception:
        pass

    try:
        content, blob_name = read_json(path.read_text())
        return content, blob_name, original_filename
    except Exception:
        pass

    try:
        content, blob_name = read_text(path.read_text())
        return content, blob_name, original_filename
    except Exception:
        pass

    content = path.read_bytes()
    blob_name = f"{hash_bytes(content)}{suffix}"
    return content, blob_name, original_filename


def read_stdin(content_type: str = None, sidecars: list | None = None) -> tuple[bytes, str, None] | None:
    """Read content from stdin. Unlike the clipboard, text is never treated as a file path."""
    data = sys.stdin.buffer.read()
    if not data:
        return

    if content_type:
        base_type = content_type.split(';')[0].strip()
        if base_type.startswith('image/'):
            with Image.open(io.BytesIO(data)) as image:
                content, blob_name = prepare_image(image)
                return content, blob_name, None
        if base_type.startswith('text/') or base_type == 'application/json':
            content, blob_name = process_text(data.decode(), content_type, sidecars, min_length=1)
            return content, blob_name, None
        # Binary content type (e.g. application/zip): upload raw bytes
        suffix = mimetypes.guess_extension(base_type) or '.bin'
        return data, f"{hash_bytes(data)}{suffix}", None

    # No content type: content sniffing waterfall
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != 'GIF':
                content, blob_name = prepare_image(image)
                return content, blob_name, None
    except Exception:
        pass

    try:
        content, blob_name = read_json(data.decode())
        return content, blob_name, None
    except Exception:
        pass

    try:
        content, blob_name = read_text(data.decode(), min_length=1)
        return content, blob_name, None
    except Exception:
        pass

    return data, f"{hash_bytes(data)}.bin", None


def build_public_url(blob, blob_name: str) -> str:
    if not URL_TEMPLATE:
        return blob.public_url
    return URL_TEMPLATE.format_map({"bucket": BUCKET_ID, "object": blob_name})


def upload_blob(content, blob_name, original_filename=None, content_type=None):
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_ID)

    if OBJECT_PREFIX:
        blob_name = OBJECT_PREFIX + blob_name
    blob = bucket.blob(blob_name)

    if blob.exists():
        return {
            "public_url": build_public_url(blob, blob_name),
            "gcs_uri": f"gs://{BUCKET_ID}/{blob_name}"
        }

    kwds = {}
    if content_type:
        kwds["content_type"] = content_type
    else:
        try:
            kwds["content_type"] = extension_to_type(Path(blob_name).suffix)
        except Exception:
            pass

    if original_filename:
        blob.content_disposition = f'inline; filename="{original_filename}"'

    blob.upload_from_string(content, **kwds)
    return {
        "public_url": build_public_url(blob, blob_name),
        "gcs_uri": f"gs://{BUCKET_ID}/{blob_name}"
    }


def get_blob_to_upload(content_type: str = None, raw_markdown: bool = False, sidecars: list | None = None) -> tuple[bytes, str, str | None] | None:
    try:
        image = ImageGrab.grabclipboard()
        if isinstance(image, PILImage):
            content, blob_name = prepare_image(image)
            return content, blob_name, None
    except Exception:
        pass

    value = pyperclip.paste()
    if not value:
        return

    try:
        return read_file(value.strip(), content_type=content_type, raw_markdown=raw_markdown, sidecars=sidecars)
    except Exception:
        pass

    if content_type:
        content, blob_name = process_text(value, content_type, sidecars)
        return content, blob_name, None

    try:
        content, blob_name = read_json(value)
        return content, blob_name, None
    except Exception:
        pass

    try:
        content, blob_name = read_text(value)
        return content, blob_name, None
    except Exception:
        pass

def read_config(env_file: Path):
    global PROJECT_ID, BUCKET_ID, OBJECT_PREFIX, JPEG_QUALITY, URL_TEMPLATE

    load_dotenv(env_file)  # loads into os.environ if file exists, won't override existing vars

    PROJECT_ID = os.environ.get("PROJECT_ID")  # type: ignore
    assert PROJECT_ID, "Missing PROJECT_ID"

    BUCKET_ID = os.environ.get("BUCKET_ID")  # type: ignore
    assert BUCKET_ID, "Missing BUCKET_ID"

    JPEG_QUALITY = os.environ.get("JPEG_QUALITY", "90")  # type: ignore
    try:
        JPEG_QUALITY = int(JPEG_QUALITY)
    except ValueError:
        raise TypeError(f"Expected JPEG_QUALITY to be an integer, received {JPEG_QUALITY}")

    OBJECT_PREFIX = os.environ.get("OBJECT_PREFIX")

    URL_TEMPLATE = os.environ.get("URL_TEMPLATE")
    if URL_TEMPLATE:
        assert "{object}" in URL_TEMPLATE, f"Expected URL_TEMPLATE to contain {{object}}, received {URL_TEMPLATE}"
        try:
            URL_TEMPLATE.format_map({"bucket": BUCKET_ID, "object": ""})
        except KeyError as e:
            raise ValueError(f"Unknown placeholder {e} in URL_TEMPLATE, expected only {{bucket}} and {{object}}")

HELP_EPILOG = """\
input sources (first match wins):
  main.py ./file.ext    upload a file
  main.py -             read stdin; also used automatically when stdin is piped
  main.py               read the clipboard (image, text, or a file path); also the
                        fallback when piped stdin is empty

--content-type is inferred from the file extension for files, and sniffed (JSON,
then text) for stdin and clipboard content. Pass it explicitly for piped
markdown, CSV, or HTML, which sniffing cannot tell apart from plain text.

environment (read from .env next to this script, or the process environment):
  PROJECT_ID     GCP project that owns the bucket (required)
  BUCKET_ID      target GCS bucket (required)
  OBJECT_PREFIX  prefix prepended to every blob name, e.g. clipboard/
  JPEG_QUALITY   quality of images re-encoded as JPEG, 0-95 (default: 90)
  URL_TEMPLATE   URL to return instead of the GCS public URL, for buckets served
                 behind a proxy. {bucket} is BUCKET_ID and {object} is the blob
                 name including OBJECT_PREFIX, e.g.
                 https://bucket-{bucket}-979839513730.us-central1.run.app/{object}

examples:
  main.py ./design.md
  main.py --content-type text/markdown <<'END'
  # Notes
  END
  echo 'SELECT 1' | main.py -o stdout
  main.py ./diagram.png

-o stdout prints {"public_url": ..., "gcs_uri": ...}; -o clipboard copies
public_url. Markdown is rendered to HTML at .../<hash>.html and its raw source
is uploaded alongside it at .../<hash>.md
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Upload content from a file, stdin, or the clipboard to Google Cloud Storage.',
                                     epilog=HELP_EPILOG,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('path', nargs='?', default=None,
                        help="Path to a file to upload, or '-' to read stdin. If omitted, reads stdin when piped, otherwise the clipboard.")
    parser.add_argument('-o', '--output', choices=['clipboard', 'stdout'], default='clipboard',
                        help='Specify where to output the resulting URL (default: clipboard)')
    parser.add_argument('--raw-markdown', action='store_true',
                        help='Upload markdown files as raw .md instead of converting to HTML')
    parser.add_argument('--content-type',
                        help='Override the content type for the uploaded file (e.g. text/plain, image/png)')
    args = parser.parse_args()

    env_file = Path(__file__).parent.joinpath(".env").resolve()
    try:
        read_config(env_file)
    except Exception as e:
        print(f"Failed to read config: {e}")
        sys.exit(1)

    content_type = args.content_type
    if content_type:
        # Lightweight "type/subtype" format validation
        assert re.match(r'^(text|image|audio|video|application|multipart|font|model)/[\w.+\-]+$', content_type), \
            f"Invalid content type: {content_type!r}"
        if content_type.startswith('text/') and 'charset' not in content_type:
            content_type += '; charset=utf-8'

    sidecars: list[tuple[bytes, str, str]] = []
    to_upload = None
    use_stdin = args.path == '-' or (args.path is None and not sys.stdin.isatty())
    if use_stdin:
        try:
            to_upload = read_stdin(content_type=content_type, sidecars=sidecars)
        except Exception as e:
            print(f"Failed to read stdin: {e}")
            sys.exit(1)
    if to_upload is None and args.path is not None and args.path != '-':
        try:
            to_upload = read_file(args.path, content_type=content_type, raw_markdown=args.raw_markdown, sidecars=sidecars)
        except Exception as e:
            print(f"Failed to read file: {e}")
            sys.exit(1)
    # Piped-but-empty stdin (e.g. `pbcopy && main.py` in an Automator action) falls back to the clipboard
    if to_upload is None and args.path is None:
        to_upload = get_blob_to_upload(content_type=content_type, raw_markdown=args.raw_markdown, sidecars=sidecars)
    if to_upload is None:
        print("Nothing to upload")
        sys.exit()

    content, blob_name, original_filename = to_upload
    # text/markdown is transformed to HTML; derive upload content type from blob_name extension instead
    upload_content_type = None if (content_type and content_type.startswith('text/markdown')) else content_type
    result = upload_blob(content, blob_name, original_filename, content_type=upload_content_type)

    for sidecar_content, sidecar_blob_name, sidecar_content_type in sidecars:
        upload_blob(sidecar_content, sidecar_blob_name, content_type=sidecar_content_type)

    if args.output == 'clipboard':
        pyperclip.copy(result["public_url"])
    else:
        print(json.dumps(result))
