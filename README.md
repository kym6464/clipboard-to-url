# clipboard-to-url

A CLI tool that uploads images, videos, or files from your clipboard to Google Cloud Storage and provides a shareable URL.

### Share an image from your clipboard

https://github.com/kym6464/clipboard-to-url/assets/36041631/96fdad65-2393-4ed4-813e-9ff444262d1b

### Share a local video file

Video plays right in the browser

https://github.com/kym6464/clipboard-to-url/assets/36041631/db849cbf-f158-408c-b3f1-a72562f6942d

### Share a local image file

Images are converted to JPG with configurable quality

https://github.com/kym6464/clipboard-to-url/assets/36041631/421d6b98-2f32-486f-8b2c-f52efb31fc80

### Share an arbitrary local file

https://github.com/kym6464/clipboard-to-url/assets/36041631/29f74632-5b50-489f-8244-7f2ba6d143d4


## Usage

(1) Copy an image, path to an image, or path to a video

(2) Run `python clipboard_to_url.py`

(3) Paste the URL

## Setup

(1) Create a bucket https://cloud.google.com/storage/docs/creating-buckets

(2) Make the bucket public by granting the `Storage Object Viewer` role to the `allUsers` principal (see [this](https://cloud.google.com/storage/docs/access-control/making-data-public) guide for more details). This allows anyone on the internet to _view_ files that are in this bucket, but only you can upload files to this bucket. When all is said and done, it should look like this:

![bucket_permissions](https://github.com/kym6464/clipboard-to-url/assets/36041631/a50e0832-ff02-4ffb-84a2-69a711fa507f)

(3) Copy `.env.example` to `.env` and fill out the values

(4) Create a python virtual environment `python -m venv env`

(5) Install dependencies `pip install wheel && pip install -r requirements.txt`
