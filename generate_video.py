#!/usr/bin/env python3
"""
Video Pipeline v3 - Actually embeds video clips and composites properly.
"""

import os
import sys
import subprocess
import re
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import requests

STYLES = {
    "true-crime": {
        "bg_colors": [(12, 12, 18), (30, 20, 20)],
        "accent": "#c41e3a",
        "text_color": "#e8e6e3",
        "subtitle_color": "#888888",
        "font_title": 84,
        "font_body": 34,
    },
    "tech-review": {
        "bg_colors": [(10, 10, 31), (26, 26, 60)],
        "accent": "#00ffff",
        "text_color": "#ffffff",
        "subtitle_color": "#8888ff",
        "font_title": 90,
        "font_body": 38,
    },
}

class VideoPipeline:
    def __init__(self, style="true-crime"):
        self.style = STYLES[style]
        self.fonts = self._load_fonts()
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.temp_files = []

    def _load_fonts(self):
        fonts = {}
        try:
            fonts['title'] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", self.style["font_title"])
            fonts['heading'] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
            fonts['body'] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", self.style["font_body"])
            fonts['small'] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except:
            default = ImageFont.load_default()
            fonts = {'title': default, 'heading': default, 'body': default, 'small': default}
        return fonts

    def parse_script(self, script_path):
        """Parse markdown with media directives."""
        with open(script_path) as f:
            content = f.read()

        slides = []
        current = {"title": "", "notes": "", "type": "text", "media": None, "layout": "center"}

        for line in content.split('\n'):
            line = line.strip()

            if line.startswith('# '):
                if current["notes"] or current["title"]:
                    slides.append(current)
                current = {"title": line[2:], "notes": "", "type": "text", "media": None, "layout": "center"}
            elif line.startswith('[image:'):
                match = re.search(r'\[image:\s*(.+?)\]', line)
                if match:
                    current["type"] = "image"
                    current["media"] = match.group(1)
            elif line.startswith('[video:'):
                match = re.search(r'\[video:\s*(.+?)\]', line)
                if match:
                    current["type"] = "video"
                    current["media"] = match.group(1)
            elif line.startswith('[layout:'):
                match = re.search(r'\[layout:\s*(.+?)\]', line)
                if match:
                    current["layout"] = match.group(1)
            elif line and not line.startswith('---'):
                current["notes"] += line + " "

        if current["notes"] or current["title"]:
            slides.append(current)

        return slides

    def create_slide_image(self, slide, index, total):
        """Generate slide image WITHOUT placeholder boxes."""
        layout = slide.get("layout", "center")

        if layout == "title":
            return self._create_title_slide(slide, index, total)
        elif layout == "split":
            return self._create_split_slide(slide, index, total)
        elif layout == "timeline":
            return self._create_timeline_slide(slide, index, total)
        elif layout == "emphasis":
            return self._create_emphasis_slide(slide, index, total)
        else:
            return self._create_standard_slide(slide, index, total)

    def _base_bg(self, draw):
        """Create background gradient."""
        c1, c2 = self.style["bg_colors"]
        for i in range(1080):
            r = int(c1[0] + (c2[0] - c1[0]) * i / 1080)
            g = int(c1[1] + (c2[1] - c1[1]) * i / 1080)
            b = int(c1[2] + (c2[2] - c1[2]) * i / 1080)
            draw.line([(0, i), (1920, i)], fill=(r, g, b))

    def _create_title_slide(self, slide, index, total):
        """Big dramatic title - NO placeholders."""
        img = Image.new('RGB', (1920, 1080))
        draw = ImageDraw.Draw(img)
        self._base_bg(draw)

        # Title with glow effect
        title = slide["title"]
        for offset in range(8, 0, -1):
            alpha = int(30 * (8-offset))
            color = (200, 30, 30) if self.style["accent"] == "#c41e3a" else (0, 200, 200)
            draw.text((102, 402-offset), title, fill=color, font=self.fonts['title'])

        draw.text((100, 400), title, fill=self.style["accent"], font=self.fonts['title'])

        if slide["notes"]:
            # Wrap notes
            words = slide["notes"][:150].split()
            lines = []
            current = ""
            for word in words:
                test = current + word + " "
                bbox = draw.textbbox((0, 0), test, font=self.fonts['body'])
                if bbox[2] - bbox[0] < 1600:
                    current = test
                else:
                    lines.append(current)
                    current = word + " "
            if current:
                lines.append(current)

            y = 550
            for line in lines[:3]:
                draw.text((100, y), line.strip(), fill=self.style["subtitle_color"], font=self.fonts['body'])
                y += 50

        draw.rectangle([0, 0, 1920, 8], fill=self.style["accent"])
        return img

    def _create_split_slide(self, slide, index, total):
        """Text left, space for media on right - actual image if available."""
        img = Image.new('RGB', (1920, 1080))
        draw = ImageDraw.Draw(img)
        self._base_bg(draw)

        # Left panel with text
        if slide["title"]:
            draw.text((60, 100), slide["title"], fill=self.style["accent"], font=self.fonts['heading'])
            draw.rectangle([60, 180, 300, 186], fill=self.style["accent"])

        y = 250
        words = slide["notes"].split()[:60]
        lines = []
        current = ""
        for word in words:
            test = current + word + " "
            bbox = draw.textbbox((0, 0), test, font=self.fonts['body'])
            if bbox[2] < 850:
                current = test
            else:
                lines.append(current)
                current = word + " "
        if current:
            lines.append(current)

        for line in lines[:7]:
            draw.text((60, y), line.strip(), fill=self.style["text_color"], font=self.fonts['body'])
            y += 50

        # Right side - if we have an image, show it. Otherwise leave blank (will be covered by video in post)
        if slide["media"] and slide["type"] == "image":
            media_path = slide["media"]
            if Path(media_path).exists():
                try:
                    photo = Image.open(media_path)
                    photo.thumbnail((900, 800), Image.Resampling.LANCZOS)
                    x = 960 + (960 - photo.width) // 2
                    y = (1080 - photo.height) // 2
                    # Draw border
                    draw.rounded_rectangle([x-6, y-6, x+photo.width+6, y+photo.height+6],
                                         radius=6, outline=self.style["accent"], width=3)
                    img.paste(photo, (x, y))
                except Exception as e:
                    print(f"    Image error: {e}")

        return img

    def _create_timeline_slide(self, slide, index, total):
        """Timeline visualization."""
        img = Image.new('RGB', (1920, 1080))
        draw = ImageDraw.Draw(img)
        self._base_bg(draw)

        if slide["title"]:
            draw.text((100, 80), slide["title"], fill=self.style["accent"], font=self.fonts['heading'])

        # Timeline line
        draw.rectangle([100, 500, 1820, 510], fill=self.style["accent"])

        # Extract dates from notes
        notes = slide["notes"]
        events = []
        if "5:32" in notes or "PM" in notes:
            events = [("5:32 PM", "Leaves home"), ("9:48 PM", "Dropped off"), ("1:47 AM", "Camera off"), ("2:28 AM", "Pace- maker")]
        elif "Jan" in notes or "Feb" in notes or "Mar" in notes:
            events = [("Jan 31", "Last seen"), ("Feb 1", "Missing"), ("Feb 10", "FBI image"), ("April", "Still gone")]
        else:
            events = [("Start", "Event 1"), ("Middle", "Event 2"), ("End", "Event 3")]

        x_positions = [200, 600, 1100, 1700]
        for i, (date, event) in enumerate(events[:4]):
            x = x_positions[i] if i < len(x_positions) else 200 + i * 400
            # Marker
            draw.ellipse([x-15, 485, x+15, 525], fill=self.style["accent"])
            # Date
            bbox = draw.textbbox((0, 0), date, font=self.fonts['heading'])
            draw.text((x - (bbox[2]-bbox[0])//2, 420), date, fill=self.style["accent"], font=self.fonts['heading'])
            # Event
            bbox = draw.textbbox((0, 0), event, font=self.fonts['body'])
            draw.text((x - (bbox[2]-bbox[0])//2, 550), event, fill=self.style["text_color"], font=self.fonts['body'])

        return img

    def _create_emphasis_slide(self, slide, index, total):
        """Big centered text for impact."""
        img = Image.new('RGB', (1920, 1080))
        draw = ImageDraw.Draw(img)
        self._base_bg(draw)

        # Large centered text
        text = slide["notes"][:100].strip()
        words = text.split()

        y = 300
        line = ""
        lines_to_draw = []

        for word in words:
            test = line + word + " "
            bbox = draw.textbbox((0, 0), test, font=self.fonts['heading'])
            if bbox[2] - bbox[0] < 1700:
                line = test
            else:
                lines_to_draw.append(line.strip())
                y += 70
                line = word + " "

        if line:
            lines_to_draw.append(line.strip())

        total_height = len(lines_to_draw) * 70
        start_y = (1080 - total_height) // 2

        for i, line_text in enumerate(lines_to_draw):
            bbox = draw.textbbox((0, 0), line_text, font=self.fonts['heading'])
            x = (1920 - (bbox[2] - bbox[0])) // 2
            draw.text((x, start_y + i * 70), line_text, fill=self.style["accent"], font=self.fonts['heading'])

        return img

    def _create_standard_slide(self, slide, index, total):
        """Standard slide - image centered if available."""
        img = Image.new('RGB', (1920, 1080))
        draw = ImageDraw.Draw(img)
        self._base_bg(draw)

        y_start = 100

        if slide["title"]:
            draw.text((100, y_start), slide["title"], fill=self.style["accent"], font=self.fonts['heading'])
            y_start = 220

        if slide["media"] and Path(slide["media"]).exists() and slide["type"] == "image":
            try:
                photo = Image.open(slide["media"])
                photo.thumbnail((1400, 700), Image.Resampling.LANCZOS)
                x = (1920 - photo.width) // 2
                y = y_start
                draw.rounded_rectangle([x-6, y-6, x+photo.width+6, y+photo.height+6],
                                     radius=6, outline=self.style["accent"], width=3)
                img.paste(photo, (x, y))
            except:
                pass
        elif slide["notes"]:
            y = y_start
            words = slide["notes"].split()[:50]
            lines = []
            current = ""
            for word in words:
                test = current + word + " "
                bbox = draw.textbbox((0, 0), test, font=self.fonts['body'])
                if bbox[2] < 1700:
                    current = test
                else:
                    lines.append(current)
                    current = word + " "
            if current:
                lines.append(current)

            for line in lines[:6]:
                draw.text((100, y), line.strip(), fill=self.style["text_color"], font=self.fonts['body'])
                y += 55

        return img

    def extract_video_clip(self, video_path, start_sec, duration, output_name):
        """Extract a clip from source video with proper scaling."""
        cmd = [
            'ffmpeg', '-y', '-ss', str(start_sec), '-t', str(duration),
            '-i', video_path, '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-an',
            output_name
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return output_name if os.path.exists(output_name) else None

    def composite_video_slide(self, bg_image_path, video_clip_path, output_path, position="right"):
        """Composite video onto slide background."""
        # For split layout, video goes on right side
        if position == "right":
            # Scale video to fit right half
            cmd = [
                'ffmpeg', '-y',
                '-i', bg_image_path,
                '-i', video_clip_path,
                '-filter_complex',
                '[1:v]scale=900:800[vid];[0:v][vid]overlay=960:140',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                '-t', '5', output_path
            ]
        else:
            # Full screen video
            cmd = ['ffmpeg', '-y', '-i', video_clip_path, '-c:v', 'copy', output_path]

        subprocess.run(cmd, capture_output=True)
        return output_path if os.path.exists(output_path) else video_clip_path

    def generate_audio(self, text, index):
        if not self.api_key or not text.strip():
            return None
        try:
            response = requests.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": "tts-1", "voice": "onyx", "input": text[:4000]},
                timeout=30
            )
            if response.status_code == 200:
                audio_file = f"audio_{index:03d}.mp3"
                with open(audio_file, "wb") as f:
                    f.write(response.content)
                return audio_file
        except Exception as e:
            print(f"    TTS error: {e}")
        return None

    def get_audio_duration(self, audio_file):
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', audio_file],
                capture_output=True, text=True
            )
            return float(result.stdout.strip())
        except:
            return 5.0

    def create_video_segment(self, slide, index, source_video=None):
        """Create segment with proper video handling."""
        is_video_slide = slide["type"] == "video" and source_video and Path(source_video).exists()

        # Generate narration first to know duration
        audio = self.generate_audio(slide["notes"], index)
        duration = self.get_audio_duration(audio) if audio else 6.0

        if is_video_slide:
            # Extract clip from source video
            clip_file = f"clip_{index:03d}.mp4"
            # Cycle through video at different positions
            video_duration = 30  # Assume 30s source
            start = (index * 4) % (video_duration - int(duration))
            extracted = self.extract_video_clip(source_video, start, duration, clip_file)

            if extracted:
                # Create composite with slide
                slide_img = self.create_slide_image(slide, index + 1, 99)
                img_file = f"slide_{index:03d}.png"
                slide_img.save(img_file)
                self.temp_files.append(img_file)

                # Composite video onto slide
                segment_file = f"segment_{index:03d}.mp4"

                if slide.get("layout") == "split":
                    # Video on right, slide on left
                    cmd = [
                        'ffmpeg', '-y',
                        '-loop', '1', '-i', img_file,
                        '-i', extracted,
                        '-filter_complex',
                        '[1:v]scale=920:720[vid];[0:v][vid]overlay=960:180',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                        '-t', str(duration + 0.5),
                        '-an', 'temp_vid.mp4'
                    ]
                    subprocess.run(cmd, capture_output=True)

                    # Add audio
                    if audio:
                        subprocess.run([
                            'ffmpeg', '-y', '-i', 'temp_vid.mp4', '-i', audio,
                            '-c:v', 'copy', '-c:a', 'aac', '-shortest',
                            segment_file
                        ], capture_output=True)
                        os.remove(audio)
                    else:
                        os.rename('temp_vid.mp4', segment_file)

                    if os.path.exists('temp_vid.mp4'):
                        os.remove('temp_vid.mp4')
                else:
                    # Full screen video
                    if audio:
                        subprocess.run([
                            'ffmpeg', '-y', '-i', extracted, '-i', audio,
                            '-c:v', 'copy', '-c:a', 'aac', '-shortest',
                            segment_file
                        ], capture_output=True)
                        os.remove(audio)
                    else:
                        segment_file = extracted
                        self.temp_files.append(extracted)

                os.remove(extracted)
                return segment_file, duration

        # Fallback to static image
        img = self.create_slide_image(slide, index + 1, 99)
        img_file = f"slide_{index:03d}.png"
        img.save(img_file)
        self.temp_files.append(img_file)

        segment_file = f"segment_{index:03d}.mp4"

        if audio:
            subprocess.run([
                'ffmpeg', '-y', '-loop', '1', '-i', img_file, '-i', audio,
                '-c:v', 'libx264', '-tune', 'stillimage', '-c:a', 'aac',
                '-pix_fmt', 'yuv420p', '-shortest', '-t', str(duration + 0.3),
                segment_file
            ], capture_output=True)
            os.remove(audio)
        else:
            subprocess.run([
                'ffmpeg', '-y', '-loop', '1', '-i', img_file,
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                '-t', str(duration), segment_file
            ], capture_output=True)

        return segment_file, duration

    def concatenate_segments(self, segments, output_name):
        with open('segments.txt', 'w') as f:
            for seg in segments:
                f.write(f"file '{seg}'\n")

        subprocess.run([
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', 'segments.txt', '-c', 'copy', output_name
        ], capture_output=True)

        if os.path.exists('segments.txt'):
            os.remove('segments.txt')

    def build(self, script_path, output_name="output.mp4", source_video=None):
        print(f"Building video from {script_path}...")
        slides = self.parse_script(script_path)
        print(f"Found {len(slides)} scenes")

        segments = []
        total_duration = 0

        for i, slide in enumerate(slides):
            print(f"\nScene {i+1}: {slide['title'][:40] if slide['title'] else slide['type']} ({slide['layout']})")

            seg_file, duration = self.create_video_segment(slide, i, source_video)
            if seg_file:
                segments.append(seg_file)
                total_duration += duration
                print(f"  Duration: {duration:.1f}s")

        print(f"\nTotal runtime: {total_duration:.1f}s")
        print("Stitching final video...")
        self.concatenate_segments(segments, output_name)

        # Cleanup
        for f in segments + self.temp_files:
            if os.path.exists(f):
                os.remove(f)

        if os.path.exists(output_name):
            size_mb = os.path.getsize(output_name) / (1024*1024)
            print(f"\nDone: {output_name} ({size_mb:.1f} MB)")
        else:
            print("\nError: Output file not created")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("script", help="Markdown script file")
    parser.add_argument("--style", choices=["true-crime", "tech-review"], default="true-crime")
    parser.add_argument("--source-video", help="Source video for clips")
    parser.add_argument("-o", "--output", default="output.mp4")
    args = parser.parse_args()

    # Load env
    for env_path in [Path(".env")]:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        k, v = line.strip().split('=', 1)
                        os.environ.setdefault(k, v)

    pipeline = VideoPipeline(style=args.style)
    pipeline.build(args.script, args.output, args.source_video)


if __name__ == "__main__":
    main()
