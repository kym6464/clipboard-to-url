# clipboard-to-url

A self-hosted program that replaces the contents of your clipboard with a shareable URL. If clipboard contains a path to a file, the file is processed.

Features:

- Basically free
- Uploads files to your very own [google cloud storage](https://cloud.google.com/storage) bucket
- Generates permalinks (unless you set an [expiration time](https://cloud.google.com/storage/docs/lifecycle))
- Converts PNG and HEIF to JPG to reduce storage size
- Videos play right in the browser
- JSON is prettified and compacted via [compact-json](https://github.com/masaccio/compact-json)
- Markdown files are converted to styled HTML (GitHub-flavored with tables, strikethrough, and autolinks) so that they're easily viewable in a web browser
- Supports all file types
- Preserves original filenames when uploading files (for "Save As" in browser)
- Integrates with Mac Finder

## Quick Start

If you have [uv](https://docs.astral.sh/uv/) installed and GCP credentials configured, you can run this directly without cloning:

```bash
PROJECT_ID=myproject BUCKET_ID=mybucket uv run https://raw.githubusercontent.com/kym6464/clipboard-to-url/main/main.py
```

Or export the variables in your shell profile for persistent use:

```bash
export PROJECT_ID=myproject
export BUCKET_ID=mybucket
export OBJECT_PREFIX=optional/prefix/  # optional
export JPEG_QUALITY=90                 # optional

uv run https://raw.githubusercontent.com/kym6464/clipboard-to-url/main/main.py
```

## One-Time Setup

1. Install [uv](https://docs.astral.sh/uv/)
2. Authenticate with google cloud https://cloud.google.com/docs/authentication/client-libraries
3. Create a bucket https://cloud.google.com/storage/docs/creating-buckets
4. Make the bucket public by granting the `Storage Object Viewer` role to the `allUsers` principal (see [this](https://cloud.google.com/storage/docs/access-control/making-data-public) guide for more details). This allows anyone on the internet to _view_ files that are in this bucket, but only you can upload files to this bucket. When all is said and done, it should look like [this](https://github.com/kym6464/clipboard-to-url/assets/36041631/a50e0832-ff02-4ffb-84a2-69a711fa507f).

## Mac Finder Integration

To integrate with [Quick Actions](https://support.apple.com/guide/mac-help/perform-quick-actions-in-the-finder-on-mac-mchl97ff9142/mac) like in the above demo, use [Automator](https://support.apple.com/guide/automator/welcome/mac) to invoke the script with files — [this](https://github.com/kym6464/clipboard-to-url/assets/36041631/eaaab735-52d5-485c-978e-9ce66ed70f74) is what the final product could look like

```
pbcopy && uv run -s "/Users/kym/repos/clipboard-to-url/main.py"
```

For more details/troubleshooting, see https://cloudinary.com/blog/upload-image-files-to-cloudinary-using-a-finder-custom-quick-action-on-a-mac

| Image                                                                                                             | Video                                                                                                             |
| ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| ![finder image](https://github.com/kym6464/clipboard-to-url/assets/36041631/fc8df94c-9d01-4d9c-9f85-ac2c6ec9aa84) | ![finder video](https://github.com/kym6464/clipboard-to-url/assets/36041631/a0506636-6c20-4014-8e89-a77f04c6a523) |

| Code                                                                                                            | Zip                                                                                                             |
| --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| ![finder yml](https://github.com/kym6464/clipboard-to-url/assets/36041631/8f05bcb2-7cdf-4b67-ad88-d2eb51e13f90) | ![finder zip](https://github.com/kym6464/clipboard-to-url/assets/36041631/58399047-8aa2-4d03-b9ef-360f98f2de35) |

## Development

(1) Clone the repo

(2) Copy `.env.example` to `.env` and fill out the values

(3) Run `uv run --script main.py`
