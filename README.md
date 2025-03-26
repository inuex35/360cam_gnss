# 360Cam GNSS

A stereoscopic/360-degree camera and GNSS data collection system for Raspberry Pi CM4. Uses PPS signal for time synchronization.

## Features

- Capture and save stereoscopic 3D video in side-by-side format using Raspberry Pi Camera Module
- Collect NMEA data from GNSS/GPS and save to GPX files
- Time synchronization using PPS (Pulse Per Second) signals
- Synchronized recording of video and GNSS data
- Automatic conversion of H.264 video to MP4 format

## Hardware Requirements

- Raspberry Pi Compute Module 4
- Raspberry Pi Camera Module(s) in stereoscopic configuration
- GNSS/GPS module (with serial communication and PPS pin)
- microSD card (high-speed and high-capacity recommended)

## Software Requirements

- Raspberry Pi OS (32-bit/64-bit)
- Python 3.6 or higher
- picamera (Python library for Raspberry Pi camera)
- OpenCV 4.x
- GPS libraries (pynmea2, gpxpy)
- RPi.GPIO
- MP4Box (from gpac package) for video conversion

## Installation

```bash
# Clone the repository
git clone https://github.com/inuex35/360cam_gnss.git
cd 360cam_gnss

# Run the installation script
bash install.sh

# After rebooting, run the program
python3 main.py
```

## Camera Setup

The system is configured to use the Raspberry Pi Camera Module in stereoscopic side-by-side (3D) mode. This is similar to using the following raspivid command:

```bash
raspivid -3d sbs -w 1280 -h 480 -t 10000 -o stereo.h264 && MP4Box -add stereo.h264 stereo.mp4
```

You can adjust the camera resolution in the `config.py` file. Note that width should be divisible by 32 and height by 16 for optimal performance with the Raspberry Pi camera.

## Usage

1. Connect Hardware
   - Connect Raspberry Pi Camera Module(s) to the CSI port
   - Connect GPS module to serial port (UART)
   - Connect GPS module's PPS pin to Raspberry Pi GPIO pin (default: GPIO18)
   
2. Edit configuration file (if needed)
   ```bash
   nano config.py
   ```
   
3. Run the program
   ```bash
   python3 main.py
   ```

4. Use the following keyboard commands during operation:
   - `r`: Start/stop recording
   - `p`: Capture a photo
   - `w`: Add a waypoint at current position
   - `i`: Toggle info display
   - `s`: Show system information
   - `q`: Quit the application

## File Structure

- `main.py`: Main program
- `config.py`: Configuration file
- `camera.py`: Camera module for stereoscopic capture
- `gnss.py`: GNSS data processing module
- `sync.py`: PPS synchronization module
- `utils.py`: Utility functions
- `data/`: Directory for saved data

## License

GPLv3
