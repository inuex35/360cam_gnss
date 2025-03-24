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
import cv2
import logging
import signal
import argparse
from datetime import datetime

# Import local modules
from config import CAMERA_CONFIG, GNSS_CONFIG, STORAGE_CONFIG, APP_CONFIG
from camera import Camera
from gnss import GNSS
from sync import SyncManager
import utils

# Global variables for signal handling
running = True

def signal_handler(sig, frame):
    """Signal handler for Ctrl+C"""
    global running
    logging.info("Signal received, stopping...")
    running = False

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='360cam_gnss - 360-degree camera and GNSS data collection system')
    
    parser.add_argument('--no-preview', dest='preview', action='store_false',
                        help='Disable camera preview window')
    parser.add_argument('--no-pps', dest='pps', action='store_false',
                        help='Disable PPS synchronization')
    parser.add_argument('--record', dest='record', action='store_true',
                        help='Start recording immediately')
    parser.add_argument('--log-level', dest='log_level', default=APP_CONFIG['log_level'],
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set logging level')
    parser.add_argument('--cam-id', dest='camera_id', type=int, default=CAMERA_CONFIG['device_id'],
                        help='Camera device ID')
    parser.add_argument('--gnss-port', dest='gnss_port', default=GNSS_CONFIG['port'],
                        help='GNSS serial port')
                        
    return parser.parse_args()

def main():
    # Parse command line arguments
    args = parse_args()
    
    # Set up logging
    log_file = utils.setup_logging(args.log_level)
    logging.info(f"Starting 360cam_gnss")
    
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Update config with command line arguments
    APP_CONFIG['enable_preview'] = args.preview
    APP_CONFIG['enable_pps_sync'] = args.pps
    CAMERA_CONFIG['device_id'] = args.camera_id
    GNSS_CONFIG['port'] = args.gnss_port
    
    # Log system information
    system_info = utils.get_system_info()
    logging.info(f"System Info: CPU: {system_info['cpu']['usage_percent']}%, "
                f"Temp: {system_info['temperature_c']}°C, "
                f"Free Disk: {system_info['disk']['free_gb']:.1f}GB")
    
    # Initialize synchronization manager
    sync_manager = None
    if APP_CONFIG['enable_pps_sync']:
        logging.info(f"Initializing PPS synchronization on GPIO pin {GNSS_CONFIG['pps_gpio_pin']}")
        sync_manager = SyncManager()
        sync_manager.start()
    
    # Initialize GNSS
    logging.info(f"Initializing GNSS module on port {GNSS_CONFIG['port']}")
    gnss = GNSS(sync_manager)
    gnss.start()
    
    # Initialize camera
    logging.info(f"Initializing 360-degree camera (ID: {CAMERA_CONFIG['device_id']})")
    camera = Camera(sync_manager)
    camera.start()
    
    # Auto-start recording if requested
    if args.record and camera.running:
        logging.info("Auto-starting recording")
        camera.start_recording()
    
    # Main loop
    try:
        last_status_time = time.time()
        recording_state = camera.recording
        
        while running:
            # Get frame for preview
            if APP_CONFIG['enable_preview'] and camera.running:
                frame = camera.get_preview_frame()
                
                if frame is not None:
                    # Add status overlay
                    frame = utils.create_status_overlay(frame, gnss, sync_manager)
                    
                    # Show the frame
                    cv2.imshow('360cam_gnss', frame)
                    
                    # Process key presses
                    key = cv2.waitKey(1) & 0xFF
                    
                    # Exit on ESC or 'q'
                    if key == 27 or key == ord(APP_CONFIG['exit_key']):
                        logging.info("Exit key pressed")
                        break
                    
                    # Toggle recording on 'r'
                    elif key == ord('r'):
                        if camera.recording:
                            camera.stop_recording()
                            logging.info("Recording stopped by user")
                        else:
                            camera.start_recording()
                            logging.info("Recording started by user")
                    
                    # Capture photo on 'c'
                    elif key == ord('c'):
                        photo_path = camera.capture_photo()
                        if photo_path:
                            logging.info(f"Photo captured: {photo_path}")
                    
                    # Add waypoint on 'w'
                    elif key == ord('w'):
                        if gnss and gnss.get_current_position():
                            waypoint_name = f"WP_{datetime.now().strftime('%H%M%S')}"
                            waypoint_id = gnss.add_waypoint(waypoint_name)
                            if waypoint_id:
                                logging.info(f"Waypoint added: {waypoint_id}")
            
            # Log periodic status (every 60 seconds)
            current_time = time.time()
            if current_time - last_status_time > 60:
                last_status_time = current_time
                
                # Log system status
                system_info = utils.get_system_info()
                logging.info(f"System Status: CPU: {system_info['cpu']['usage_percent']}%, "
                            f"Temp: {system_info['temperature_c']}°C, "
                            f"Free Disk: {system_info['disk']['free_gb']:.1f}GB")
                
                # Log GNSS status
                if gnss and gnss.get_current_position():
                    lat, lon, alt = gnss.get_current_position()
                    fix_info = gnss.get_fix_info()
                    logging.info(f"GNSS Status: Pos: {lat:.6f}, {lon:.6f}, Alt: {alt:.1f}m, "
                                f"Sats: {fix_info['satellites']}, Quality: {fix_info['quality']}")
                else:
                    logging.info("GNSS Status: No Fix")
                
                # Log PPS status
                if sync_manager and sync_manager.get_last_pps_time():
                    pps_time = sync_manager.get_last_pps_time().strftime('%H:%M:%S.%f')[:-3]
                    stability = sync_manager.get_pps_stability()
                    logging.info(f"PPS Status: Last: {pps_time}, Stability: {stability:.2f}")
            
            # Sleep to prevent high CPU usage
            time.sleep(0.01)
            
            # Check if recording state has changed
            if camera.recording != recording_state:
                recording_state = camera.recording
                if recording_state:
                    logging.info(f"Recording started: {camera.current_video_path}")
                else:
                    logging.info("Recording stopped")
    
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received")
    
    except Exception as e:
        logging.exception(f"Unexpected error: {str(e)}")
    
    finally:
        # Clean up
        logging.info("Cleaning up...")
        
        if camera.recording:
            camera.stop_recording()
        
        camera.stop()
        gnss.stop()
        
        if sync_manager:
            sync_manager.stop()
        
        if APP_CONFIG['enable_preview']:
            cv2.destroyAllWindows()
        
        logging.info("360cam_gnss stopped")

if __name__ == "__main__":
    main()
