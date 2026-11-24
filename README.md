# FieldGuide

**See an object. Understand it. Learn how to use it.**

FieldGuide is an AI-powered visual task assistant that turns your webcam into an interactive guide. Point your camera at an everyday object, select its bounding box, and FieldGuide provides step-by-step instructions, safety cautions, and relevant YouTube tutorials.

Built as a **Problem-Based Learning (PBL) project**.

![FieldGuide Demo](docs/screenshot_demo.png)

## Features

- **Real-time object detection:** Detects and tracks objects using YOLO11 and ByteTrack.
- **Interactive selection:** Select an object directly from the camera feed.
- **Step-by-step guidance:** Displays instructions and important cautions for supported objects.
- **YouTube tutorials:** Finds relevant video tutorials when an API key is configured.
- **Voice assistance:** Reads instructions aloud using Piper neural text-to-speech.
- **Local processing:** Camera frames are processed on your machine. They are not uploaded to a cloud service by the current detection pipeline.
- **Video input:** Supports webcam feeds and prerecorded video files.

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python |
| Interface | PySide6 |
| Object detection | YOLO11 |
| Object tracking | ByteTrack |
| Computer vision | OpenCV |
| Voice assistance | Piper TTS |
| Tutorial discovery | YouTube Data API v3 |
| Local caching | SQLite |

## Quick Start

### Requirements

- Arch Linux
- Python 3.10 or newer
- Webcam or video file
- Internet connection for initial model download and YouTube search
- Piper TTS and a compatible voice model for voice assistance

### 1. Install system dependencies

```bash
sudo pacman -S python python-pip alsa-utils
```

Install Piper through your preferred Arch package source. For example, using an AUR helper:

```bash
yay -S piper-tts
```

### 2. Clone the repository

```bash
git clone https://github.com/gc-MayankPun/FieldGuide.git
cd FieldGuide
```

### 3. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 4. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Piper

Download a Piper voice model and its matching configuration file.

The default model used by FieldGuide is:

`en_US-lessac-medium.onnx`

Place both files in:

```text
~/.local/share/fieldguide/voices/
```

The expected files are:

```text
en_US-lessac-medium.onnx
en_US-lessac-medium.onnx.json
```

### 6. Configure YouTube (Optional)

Copy the example environment file:

```bash
cp .env.example .env
```

Add your YouTube Data API v3 key:

```env
YOUTUBE_API_KEY=your_api_key_here
```

You can use FieldGuide without a YouTube API key. Local guidance will still be available.

### 7. Launch FieldGuide

```bash
python -m fieldguide --start
```

Alternatively:

```bash
scripts/run.sh --start
```

On the first launch, Ultralytics downloads the YOLO11 model weights if they are not already available.

## Using FieldGuide

| Action | How |
|---|---|
| Start / stop camera | Toolbar button or `Ctrl+R` |
| Select an object | Click its bounding box |
| Clear selection | Click empty space or press `Esc` |
| Adjust detection sensitivity | Use the confidence slider |
| Listen to instructions | Use the speech button |
| Stop speech | Use the speech control |
| Open a tutorial | Select a video from the tutorial list |
| Search YouTube manually | Use the YouTube search fallback |
| Use a video file | `python -m fieldguide --video clip.mp4` |
| Select another webcam | `python -m fieldguide --camera 1` |

A solid bounding box indicates a stable track, while a dashed box indicates that the track is still settling.

The status bar displays information such as the processing backend, camera resolution, FPS, inference time, and tracked objects.

## Object Recognition

FieldGuide currently uses the standard YOLO11 pretrained model, which recognises objects from its supported COCO classes.

This means some specific objects, brands, or object variations may receive a broader label. For example, a particular drink can may be identified as a bottle.

Object detection and object understanding are separate tasks. YOLO identifies and tracks objects, while FieldGuide uses the resulting label to retrieve relevant guidance.

**Future direction:** Integrating an optional vision-language AI model to identify less common objects and generate contextual instructions without requiring a manually written entry for every object.

## YouTube Tutorials

FieldGuide uses the YouTube Data API v3 to discover relevant tutorials.

To enable it:

1. Create a project in Google Cloud Console.
2. Enable YouTube Data API v3.
3. Create an API key.
4. Add the key to your `.env` file.

Search results are cached in `data/cache.sqlite3` to reduce API requests.

If the API key is missing, the application can still provide local instructions and open a normal YouTube search page.

## Voice Assistance

FieldGuide uses Piper, a local neural text-to-speech engine, to read instructions aloud.

Voice generation and playback run outside the main interface thread, allowing the camera and UI to remain responsive.

Voice processing is local and does not require an external speech API.

## Performance

FieldGuide separates camera capture, inference, and interface rendering into independent threads.

A latest-frame strategy ensures that slow inference does not build up a queue of outdated camera frames.

The interface continues rendering the latest available detection results while inference processes incoming frames.

To benchmark performance:

```bash
python -m fieldguide.benchmark --video clip.mp4 --frames 300
```

The benchmark reports mean and 95th-percentile inference time, FPS, and label changes with and without label stabilisation.

## Tests

Run the test suite:

```bash
pytest -q
```

The tests use a fake detector, so a physical camera and downloaded YOLO weights are not required. UI tests run headlessly using Qt's offscreen platform.

## Privacy

Object detection and tracking run locally on the machine.

The current detection pipeline does not upload camera frames to an external service. When YouTube integration is enabled, a short text search query is sent to YouTube to retrieve tutorials.

Future cloud-based AI features, if enabled, may require sending a selected image to an external AI provider. Such functionality should be optional and clearly disclosed.

## Licence

Ultralytics YOLO is distributed under AGPL-3.0, with separate commercial licensing available. Review the applicable licence terms before redistributing or commercially deploying FieldGuide.