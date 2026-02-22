## Project Overview
This is a Python script that uploads content from clipboard or files to Google Cloud Storage and returns public URLs. The script handles various content types including images, JSON, CSV, HTML, and text files.

## Environment & Execution
- **Python execution**: Use `uv run --script main.py` (NOT regular python commands)
- **Testing**: Use `uv run python3 -c "..."` for testing code snippets
- **Dependencies**: Managed via inline script dependencies in main.py header

### Testing Commands
```bash
# Test with escaped path
echo "/path/with\ spaces/file.jpg" | pbcopy && uv run --script main.py -o stdout

# Test function logic
uv run python3 -c "from main import unescape_shell_path; print(repr(unescape_shell_path('test\\ path')))"
```

## Testing Approach
- Test problematic paths with spaces/special chars: `/some/path/FILE\'S\ NAME\ WITH\ SPACES.jpg`
- Use clipboard simulation: `echo "path" | pbcopy && uv run --script main.py -o stdout`
- Verify file existence after path processing

## Architecture & Processing Flow

### Core Components
- `get_blob_to_upload(content_type, raw_markdown)`: Main entry point
- `read_file(path_str, content_type, raw_markdown)`: Handles file path processing (quotes removal → shell unescaping → file operations)
- `process_text(value, content_type)`: Routes text content to the appropriate processor based on content type
- Content processors: `read_json()`, `read_csv()`, `read_html()`, `read_markdown()`, `read_text()`, `prepare_image()`
- `upload_blob()`: GCS upload with deduplication

### Content Type Resolution (three tiers, in priority order)
1. **`--content-type` flag**: Routes directly to the matching processor; `text/markdown` renders to HTML (uploaded as `text/html`)
2. **File suffix**: Recognized extensions (`.json`, `.csv`, `.html`, `.md`, image types, `.txt`) dispatch directly
3. **Content sniffing waterfall**: Used for unrecognized suffixes and `.md` with `--raw-markdown` — tries image (PIL) → JSON → text → raw bytes

### Processing Patterns
- **File processing pipeline**: quotes removal → shell unescaping → path validation → content type resolution
- **Error handling**: Use assertions with descriptive messages
- **Hashing**: MD5 for content-based deduplication