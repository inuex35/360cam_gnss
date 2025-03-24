#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2025 inuex35
#
# This file is part of 360cam_gnss.
#
# 360cam_gnss is free software: you can redistribute it 
# and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3 of the 
# License, or (at your option) any later version.
#

# Camera settings
CAMERA_CONFIG = {
    'device_id': 0,                   # Camera device ID (usually 0)
    'width': 1920,                    # Image width
    'height': 1080,                   # Image height
    'fps': 30,                        # Frame rate
    'codec': 'XVID',                  # Video codec
    'extension': '.avi',              # Video file extension
    'capture_interval': 0,            # Capture interval in seconds for time-lapse (0 for continuous recording)
    'photo_extension': '.jpg',        # Photo file extension
    'preview_width': 800,             # Preview window width
    'preview_height': 450             # Preview window height
}

# GNSS settings
GNSS_CONFIG = {
    'port': '/dev/ttyAMA0',           # Serial port
    'baudrate': 9600,                 # Baud rate
    'parity': 'N',                    # Parity
    'stopbits': 1,                    # Stop bits
    'timeout': 1,                     # Timeout in seconds
    'log_interval': 1,                # GNSS data logging interval in seconds
    'gpx_extension': '.gpx',          # GPX file extension
    'nmea_extension': '.nmea',        # NMEA file extension
    'pps_gpio_pin': 18                # GPIO pin number for PPS signal
}

# Storage settings
STORAGE_CONFIG = {
    'base_path': './data',            # Base path for data storage
    'video_dir': 'videos',            # Directory for video storage
    'photo_dir': 'photos',            # Directory for photo storage
    'gnss_dir': 'gnss',               # Directory for GNSS data storage
    'sync_dir': 'sync',               # Directory for synchronization info storage
    'timestamp_format': '%Y%m%d_%H%M%S',  # Timestamp format
    'use_timestamp_subdir': True      # Create subdirectories by date
}

# Application settings
APP_CONFIG = {
    'log_level': 'INFO',              # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    'enable_preview': True,           # Enable camera preview
    'save_on_exit': True,             # Save data on exit
    'enable_pps_sync': True,          # Enable PPS synchronization
    'exit_key': 'q'                   # Exit key
}
