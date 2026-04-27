WATERMARK SETUP
===============

Place your watermark logo file here as: watermark.png

Requirements:
- Format: PNG with transparent background
- Recommended size: 500x500 pixels or larger (will be scaled automatically)
- The watermark will appear in the bottom-right corner of all video clips

To create the watermark:
1. Go to remove.bg or canva.com
2. Upload your logo image
3. Remove the background to make it transparent
4. Download as PNG
5. Save here as: watermark.png

Configuration (in .env file):
- WATERMARK_ENABLED=true (default)
- WATERMARK_OPACITY=0.3 (30% transparency, range: 0.0 to 1.0)
- WATERMARK_SCALE=0.1 (10% of video width)
- WATERMARK_POSITION=bottom_right (options: bottom_right, bottom_left, top_right, top_left)
- WATERMARK_MARGIN=20 (pixels from edge)
