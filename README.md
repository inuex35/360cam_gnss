# 360Cam GNSS

A 360-degree camera and GNSS data collection system for Raspberry Pi CM4. Uses PPS signal for time synchronization.

## Features

- Capture and save video from 360-degree cameras
- Collect NMEA data from GNSS/GPS and save to GPX files
- Time synchronization using PPS (Pulse Per Second) signals
- Synchronized recording of video and GNSS data

## Hardware Requirements

- Raspberry Pi Compute Module 4
- 360-degree camera (USB camera compatible with OpenCV)
- GNSS/GPS module (with serial communication and PPS pin)
- microSD card (high-speed and high-capacity recommended)

## Software Requirements

- Raspberry Pi OS (32-bit/64-bit)
- Python 3.6 or higher
- OpenCV 4.x
- GPS libraries (pynmea2, gpxpy)
- RPi.GPIO

## Installation

```bash
# Install required packages
sudo apt-get update
sudo apt-get install -y python3-opencv python3-pip python3-rpi.gpio gpsd gpsd-clients

# Install Python libraries
pip3 install pynmea2 gpxpy

# Clone the repository
git clone https://github.com/inuex35/360cam_gnss.git
cd 360cam_gnss
```

## Usage

1. Connect Hardware
   - Connect 360-degree camera to USB port
   - Connect GPS module to serial port (UART)
   - Connect GPS module's PPS pin to Raspberry Pi GPIO pin (default: GPIO18)
   
2. Edit configuration file
   ```bash
   nano config.py
   ```
   
3. Run the program
   ```bash
   python3 main.py
   ```

## File Structure

- `main.py`: Main program
- `config.py`: Configuration file
- `camera.py`: 360-degree camera module
- `gnss.py`: GNSS data processing module
- `sync.py`: PPS synchronization module
- `utils.py`: Utility functions
- `data/`: Directory for saved data

## License

GPLv3
