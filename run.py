#!/usr/bin/env python3
"""
Video Clips Extractor - FastAPI Server Entry Point

Usage:
    python run.py
    python run.py --host 0.0.0.0 --port 8080
    python run.py --reload  # Development mode
"""

import argparse
import uvicorn

from app.core.config import settings


def main():
    """Run the FastAPI server."""
    parser = argparse.ArgumentParser(
        description="Video Clips Extractor API Server"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=settings.HOST,
        help=f"Host to bind to (default: {settings.HOST})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.PORT,
        help=f"Port to bind to (default: {settings.PORT})"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )

    args = parser.parse_args()

    print(f"\nStarting Video Clips Extractor API...")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Reload: {args.reload}")
    print(f"Workers: {args.workers}")
    print(f"\nOpen in browser: http://localhost:{args.port}/")
    print(f"API docs: http://localhost:{args.port}/docs\n")

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level="info",
    )


if __name__ == "__main__":
    main()
