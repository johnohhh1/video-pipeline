# video-pipeline

Turns a short Markdown script into a narrated 1080p explainer or documentary-style video. Each section becomes a slide with its own layout, optional images or clips cut from a source video, and AI text-to-speech narration, all stitched together with FFmpeg.

## Install

Requires Python 3.9+, [FFmpeg](https://ffmpeg.org/) on your `PATH`, and an OpenAI API key for narration.

```bash
git clone https://github.com/johnohhh1/video-pipeline
cd video-pipeline
pip install -r requirements.txt
cp .env.example .env        # then put your OpenAI key in .env
```

Without a key the video still renders, just with no narration.

## Usage

```bash
python generate_video.py SCRIPT.md [-o output.mp4] [--style true-crime|tech-review] [--source-video clip-source.mp4]
```

Try the included example:

```bash
python generate_video.py examples/example-script.md --style tech-review -o transistor.mp4
```

| Option | Meaning |
|---|---|
| `-o`, `--output` | Output file (default `output.mp4`) |
| `--style` | Color/typography preset: `true-crime` (dark, red accents; default) or `tech-review` |
| `--source-video` | Video to pull clips from for `[video: ...]` scenes |

## Writing a script

Separate scenes with `---`. Each scene has a `#` title, an optional layout and media tag, and narration text:

```markdown
# Main Title
[layout: title]
This text becomes the narration for the scene.

---

# With Footage
[layout: split]
[video: source.mp4]
Narration while the clip plays on the right.
```

**Layouts:** `title` (big title with glow), `split` (text left, media right), `timeline` (horizontal timeline), `emphasis` (large centered statement), `center` (default).

**Media:** `[image: path.jpg]` shows a still image. `[video: source.mp4]` cuts a clip from the file given with `--source-video`.

Each scene lasts as long as its narration. Output is 1920×1080.

## Contributing

Issues and pull requests are welcome, for example new layouts or styles, other TTS providers, or subtitle burn-in.

## License

MIT, see [LICENSE](LICENSE).
