#!/bin/bash
# run this once before pip install

# portaudio is required for pyaudio on macOS
brew install portaudio

pip install -r requirements.txt
