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
    python3-picamera \
    python3-rpi.gpio \
    gpsd \
    gpsd-clients \
    libatlas-base-dev \
    libopenjp2-7 \
    libtiff5 \
    gpac  # Provides MP4Box for video conversion

# Install Python dependencies
pip3 install pynmea2 gpxpy pyserial picamera

# Create data directories
mkdir -p data/videos data/photos data/gnss data/sync data/logs data/backups

# Set permissions
chmod +x main.py

# Set up camera
echo "Enabling camera module..."
if ! grep -q "^start_x=1" /boot/config.txt; then
    sudo bash -c "echo 'start_x=1' >> /boot/config.txt"
fi

if ! grep -q "^gpu_mem=128" /boot/config.txt; then
    sudo bash -c "echo 'gpu_mem=128' >> /boot/config.txt"
fi

echo "Installation complete!"
echo "The system needs to be rebooted to enable the camera module."
echo "After rebooting, run the program with: python3 main.py"
echo ""
read -p "Would you like to reboot now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
fi
