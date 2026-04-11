# Video Clips Extractor

Automatically extract engaging 60-90 second clips from long videos for TikTok and YouTube Shorts.

## Features

- **Automatic transcription** using OpenAI Whisper (local, free)
- **AI-powered engagement analysis** to find viral-worthy moments
- **Smart clip selection** that avoids mid-sentence cuts
- **Vertical video conversion** (9:16) with blur padding
- **Auto-generated subtitles** burned into clips
- **Pluggable LLM providers** - easily switch between Ollama, Groq, Together AI

## Quick Start

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install FFmpeg

**Windows:**
```bash
winget install Gyan.FFmpeg
```
Or download from https://www.gyan.dev/ffmpeg/builds/

**Mac:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg
```

### 3. Setup API Key

Edit the `.env` file and add your API key:

```env
# Google Gemini (Recommended - Free)
# Get key at: https://aistudio.google.com/apikey
GEMINI_API_KEY=your_gemini_key_here
```

**Available LLM Providers:**

| Provider | Get API Key | Free Tier |
|----------|-------------|-----------|
| **Gemini** (default) | https://aistudio.google.com/apikey | 1500 req/day |
| Groq | https://console.groq.com | 14400 req/day |
| Together | https://together.ai | $25 credit |
| Ollama | https://ollama.ai | Unlimited (local) |

### 4. Run the Pipeline

```bash
python main.py your_video.mp4
```

## Usage Examples

```bash
# Basic usage
python main.py video.mp4

# Extract only 3 clips
python main.py video.mp4 --num-clips 3

# Use Groq instead of Ollama
python main.py video.mp4 --provider groq --model llama3-70b-8192

# Skip vertical conversion
python main.py video.mp4 --no-vertical

# Skip subtitles
python main.py video.mp4 --no-subtitles

# Reuse existing transcription (faster iteration)
python main.py video.mp4 --skip-transcription

# Keep temporary files for debugging
python main.py video.mp4 --no-cleanup
```

## Configuration

Edit `config.py` to customize behavior:

```python
# Whisper model size (tiny/base/small/medium/large)
WHISPER_MODEL = "small"

# LLM provider (ollama/groq/together)
LLM_PROVIDER = "ollama"
LLM_MODEL = "mistral"

# Clip settings
MIN_CLIP_DURATION = 60  # seconds
MAX_CLIP_DURATION = 90  # seconds
NUM_CLIPS = 5

# Output settings
VERTICAL_MODE = True
VERTICAL_METHOD = "blur"  # or "crop"
ADD_SUBTITLES = True
```

## Project Structure

```
Video_Clips/
├── main.py                 # Main pipeline entry point
├── config.py               # Configuration settings
├── requirements.txt        # Python dependencies
├── modules/
│   ├── transcriber.py      # Whisper transcription
│   ├── analyzer.py         # LLM engagement analysis
│   ├── clip_selector.py    # Clip selection logic
│   ├── video_cutter.py     # FFmpeg video cutting
│   └── subtitle_generator.py  # SRT generation
├── llm_providers/          # Pluggable LLM backends
│   ├── ollama_provider.py
│   ├── groq_provider.py
│   └── together_provider.py
├── prompts/
│   └── engagement_prompt.txt
├── input/                  # Place videos here
├── output/clips/           # Generated clips
└── temp/                   # Temporary files
```

## How It Works

1. **Transcription**: Uses Whisper to convert speech to text with timestamps
2. **Analysis**: LLM identifies engaging segments (hooks, emotional moments, insights)
3. **Selection**: Validates clips, adjusts boundaries to avoid mid-sentence cuts
4. **Cutting**: FFmpeg extracts clips, optionally converts to 9:16 vertical
5. **Subtitles**: Burns transcription as subtitles into clips

## Switching LLM Providers

The system uses a pluggable architecture. To switch providers:

**Step 1:** Add your API key to `.env`:
```env
GEMINI_API_KEY=your_key
GROQ_API_KEY=your_key
TOGETHER_API_KEY=your_key
```

**Step 2:** Change provider in `config.py`:
```python
LLM_PROVIDER = "gemini"  # or "groq", "together", "ollama"
LLM_MODEL = "gemini-1.5-flash"
```

No other code changes needed!

## Sample Output

### Transcription JSON
```json
{
  "text": "Full transcript...",
  "duration": 1847.52,
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 3.5,
      "text": "Hey everyone, welcome back!",
      "words": [...]
    }
  ]
}
```

### Analysis JSON
```json
{
  "clips": [
    {
      "start": "02:15",
      "end": "03:30",
      "score": 9,
      "hook": "Here's what nobody tells you...",
      "reason": "Strong curiosity hook, valuable insight",
      "type": "insight"
    }
  ]
}
```

### Final Clips JSON
```json
{
  "clips": [
    {
      "clip_number": 1,
      "filename": "clip_001.mp4",
      "start_seconds": 135.0,
      "end_seconds": 207.5,
      "duration": 72.5,
      "score": 9
    }
  ]
}
```

## Hardware Requirements

- **Minimum**: 8GB RAM, CPU only (slow but works)
- **Recommended**: 16GB RAM, NVIDIA GPU with 6GB+ VRAM
- **Storage**: ~10GB for Whisper models + temp files

## Troubleshooting

### "FFmpeg not found"
Make sure FFmpeg is installed and in your PATH. Run `ffmpeg -version` to test.

### "Ollama not available"
1. Make sure Ollama is running: `ollama serve`
2. Make sure you have a model: `ollama list`
3. Pull a model if needed: `ollama pull mistral`

### "CUDA out of memory"
Try a smaller Whisper model in config.py:
```python
WHISPER_MODEL = "base"  # or "tiny"
```

### Slow transcription
- Use GPU if available (check `USE_GPU = True` in config)
- Use smaller Whisper model ("base" instead of "small")
- Split very long videos manually

### No clips found
- Lower `MIN_VIRALITY_SCORE` in config.py
- Increase `NUM_CLIPS` to consider more options
- Check that your video has clear speech

## License

MIT License - Free for personal and commercial use.
