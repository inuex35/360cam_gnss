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

import os
import sys
import time
import logging
import cv2
import numpy as np
from datetime import datetime
import psutil
import subprocess

def setup_logging(level='INFO'):
    """
    Set up logging configuration
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create logs directory if it doesn't exist
    if not os.path.exists('./logs'):
        os.makedirs('./logs')
    
    # Set up file handler
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'./logs/360cam_gnss_{timestamp}.log'
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Log start message
    logging.info(f"Log started at {timestamp}")
    logging.info(f"Log level set to {level}")
    
    return log_file

def get_system_info():
    """
    Get system information
    
    Returns:
        dict: System information
    """
    # CPU info
    cpu_usage = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq()
    cpu_count = psutil.cpu_count()
    
    # Memory info
    memory = psutil.virtual_memory()
    
    # Disk info
    disk = psutil.disk_usage('/')
    
    # Temp info
    try:
        temp_output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode('utf-8')
        temp = temp_output.replace('temp=', '').replace("'C", '')
    except:
        temp = "N/A"
    
    system_info = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'cpu': {
            'usage_percent': cpu_usage,
            'frequency_mhz': cpu_freq.current if cpu_freq else "N/A",
            'cores': cpu_count
        },
        'memory': {
            'total_mb': memory.total / (1024 * 1024),
            'available_mb': memory.available / (1024 * 1024),
            'used_percent': memory.percent
        },
        'disk': {
            'total_gb': disk.total / (1024 * 1024 * 1024),
            'free_gb': disk.free / (1024 * 1024 * 1024),
            'used_percent': disk.percent
        },
        'temperature_c': temp
    }
    
    return system_info

def create_text_overlay(frame, text_items):
    """
    Create a text overlay on a frame
    
    Args:
        frame: Input frame
        text_items: List of (text, position, color, font_scale) tuples
        
    Returns:
        frame: Frame with text overlay
    """
    for text, position, color, font_scale in text_items:
        cv2.putText(
            frame,
            text,
            position,
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            color,
            2
        )
    
    return frame

def create_status_overlay(frame, gnss, sync_manager=None):
    """
    Create a status overlay for camera preview
    
    Args:
        frame: Input frame
        gnss: GNSS instance
        sync_manager: SyncManager instance
        
    Returns:
        frame: Frame with status overlay
    """
    height, width = frame.shape[:2]
    
    # Create a semi-transparent overlay for text background
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, height - 160), (350, height - 10), (0, 0, 0), -1)
    
    # Add overlay with transparency
    alpha = 0.7
    frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
    
    # Get current time
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Get system info
    system_info = get_system_info()
    
    # Create text items
    text_items = [
        (f"Time: {now}", (20, height - 130), (255, 255, 255), 0.5),
        (f"CPU: {system_info['cpu']['usage_percent']}% | Temp: {system_info['temperature_c']}°C", 
         (20, height - 110), (255, 255, 255), 0.5),
        (f"Storage: {system_info['disk']['free_gb']:.1f}GB free", 
         (20, height - 90), (255, 255, 255), 0.5)
    ]
    
    # Add GNSS info if available
    if gnss and gnss.get_current_position():
        lat, lon, alt = gnss.get_current_position()
        fix_info = gnss.get_fix_info()
        
        text_items.extend([
            (f"GPS: {lat:.6f}, {lon:.6f}, Alt: {alt:.1f}m", 
             (20, height - 70), (100, 255, 100), 0.5),
            (f"Satellites: {fix_info['satellites']} | Quality: {fix_info['quality']} | HDOP: {fix_info['hdop']:.1f}", 
             (20, height - 50), (100, 255, 100), 0.5)
        ])
    else:
        text_items.append(
            ("GPS: No Fix", (20, height - 70), (255, 100, 100), 0.5)
        )
    
    # Add PPS info if available
    if sync_manager and sync_manager.get_last_pps_time():
        pps_time = sync_manager.get_last_pps_time().strftime('%H:%M:%S.%f')[:-3]
        stability = sync_manager.get_pps_stability()
        
        # Color based on stability
        if stability > 0.9:
            color = (100, 255, 100)  # Green
        elif stability > 0.7:
            color = (100, 255, 255)  # Yellow
        else:
            color = (100, 100, 255)  # Red
            
        text_items.append(
            (f"PPS: {pps_time} | Stability: {stability:.2f}", 
             (20, height - 30), color, 0.5)
        )
    else:
        text_items.append(
            ("PPS: Not available", (20, height - 30), (255, 100, 100), 0.5)
        )
    
    return create_text_overlay(frame, text_items)

def convert_nmea_to_gpx(nmea_file, gpx_file):
    """
    Convert NMEA file to GPX format
    
    Args:
        nmea_file: Input NMEA file path
        gpx_file: Output GPX file path
        
    Returns:
        bool: Success status
    """
    try:
        import pynmea2
        import gpxpy
        import gpxpy.gpx
        
        # Create GPX object
        gpx = gpxpy.gpx.GPX()
        
        # Create track
        track = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(track)
        
        # Create segment
        segment = gpxpy.gpx.GPXTrackSegment()
        track.segments.append(segment)
        
        # Parse NMEA file
        with open(nmea_file, 'r') as f:
            for line in f:
                try:
                    # Extract NMEA from log line if needed
                    if ' $' in line:
                        parts = line.split(' $')
                        if len(parts) > 1:
                            nmea = '$' + parts[1].strip()
                        else:
                            continue
                    elif line.startswith('$'):
                        nmea = line.strip()
                    else:
                        continue
                    
                    # Parse NMEA sentence
                    msg = pynmea2.parse(nmea)
                    
                    # Process GGA messages with valid position
                    if isinstance(msg, pynmea2.GGA) and msg.latitude and msg.longitude:
                        point = gpxpy.gpx.GPXTrackPoint(
                            latitude=msg.latitude,
                            longitude=msg.longitude,
                            elevation=msg.altitude,
                            time=datetime.combine(
                                datetime.now().date(),
                                datetime.strptime(msg.timestamp.strftime('%H%M%S.%f'), '%H%M%S.%f').time()
                            )
                        )
                        segment.points.append(point)
                except Exception as e:
                    logging.error(f"Error parsing NMEA line: {e}")
                    continue
        
        # Write GPX file
        with open(gpx_file, 'w') as f:
            f.write(gpx.to_xml())
        
        logging.info(f"Converted {nmea_file} to {gpx_file} with {len(segment.points)} points")
        return True
    
    except Exception as e:
        logging.error(f"Error converting NMEA to GPX: {e}")
        return False

def get_available_cameras():
    """
    Get list of available camera devices
    
    Returns:
        list: List of available camera indices
    """
    available_cameras = []
    
    # Try all camera indices from 0 to 10
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available_cameras.append(i)
            cap.release()
    
    return available_cameras
