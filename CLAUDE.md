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
- `get_blob_to_upload()`: Main entry point that tries different content types
- `read_file()`: Handles file path processing (quotes removal → shell unescaping → file operations)
- Content processors: `read_json()`, `read_csv()`, `read_html()`, `read_text()`, `prepare_image()`
- `upload_blob()`: GCS upload with deduplication

### Processing Patterns
1. **File processing pipeline**: quotes removal → shell unescaping → path validation → content type detection
2. **Content type detection**: Try image → JSON → CSV/HTML (by extension) → text → raw bytes
3. **Error handling**: Use assertions with descriptive messages
4. **Hashing**: MD5 for content-based deduplication