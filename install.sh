#!/bin/bash

# Installation script for 360cam_gnss

echo "Installing 360cam_gnss dependencies..."

# Update package lists
sudo apt-get update

# Install system dependencies
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-opencv \
    python3-rpi.gpio \
    gpsd \
    gpsd-clients \
    libatlas-base-dev \
    libopenjp2-7 \
    libtiff5

# Install Python dependencies
pip3 install pynmea2 gpxpy pyserial

# Create data directories
mkdir -p data/videos data/photos data/gnss data/sync data/logs data/backups

# Set permissions
chmod +x main.py

echo "Installation complete!"
echo "Run the program with: python3 main.py"
