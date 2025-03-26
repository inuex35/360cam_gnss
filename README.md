# 360Cam GNSS

A real-time stereoscopic/360-degree camera viewer and data recorder for Raspberry Pi CM4. Uses PPS signal for time synchronization with GNSS data.

## Features

- **Real-time display** of stereoscopic 3D video from Raspberry Pi Camera Module
- Multiple viewing modes:
  - **Side-by-Side**: Standard stereoscopic view
  - **Left/Right**: Individual camera views
  - **Anaglyph**: Red-cyan 3D mode for use with 3D glasses
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

## Display Modes

The application supports multiple viewing modes for the stereoscopic camera:

- **Side-by-Side (default)**: Shows the full stereoscopic view
- **Left**: Shows only the left camera view
- **Right**: Shows only the right camera view
- **Anaglyph**: Creates a red-cyan 3D image for viewing with anaglyph 3D glasses

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
   - `f`: Toggle FPS display
   - `F`: Toggle fullscreen mode
   - `d`: Cycle through display modes
   - `1`: Side-by-side display mode
   - `2`: Left camera only
   - `3`: Right camera only
   - `4`: Anaglyph (red-cyan) mode
   - `s`: Show system information
   - `q`: Quit the application

## Performance Considerations

For best performance:
- Use a Raspberry Pi CM4 with at least 2GB of RAM
- Use a Class 10 or UHS-I microSD card
- Close unnecessary applications while running
- If using a battery, ensure it can provide sufficient power

## File Structure

- `main.py`: Main program
- `config.py`: Configuration file
- `camera.py`: Camera module for stereoscopic capture and real-time display
- `gnss.py`: GNSS data processing module
- `sync.py`: PPS synchronization module
- `utils.py`: Utility functions
- `data/`: Directory for saved data

## License

GPLv3
