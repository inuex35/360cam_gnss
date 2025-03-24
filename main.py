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

import cv2
import time
import sys
import os
import signal
import logging
from datetime import datetime

# Import our modules
from config import CAMERA_CONFIG, GNSS_CONFIG, STORAGE_CONFIG, APP_CONFIG
from camera import Camera
from gnss import GNSS
from sync import SyncManager
import utils

class MainApplication:
    """Main application class for 360cam_gnss"""
    
    def __init__(self):
        """Initialize the application"""
        # Setup logging
        self.logger = utils.setup_logging()
        self.logger.info("Initializing 360cam_gnss application")
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Check dependencies
        if not utils.check_dependencies():
            self.logger.error("Missing dependencies. Exiting.")
            sys.exit(1)
        
        # Check storage space
        if not utils.check_storage_space():
            self.logger.warning("Low storage space. Some data may not be saved.")
        
        # Backup configuration
        utils.backup_config()
        
        # Initialize components
        self.logger.info("Initializing system components")
        
        # Create sync manager first
        self.sync_manager = SyncManager()
        
        # Create camera and GNSS modules with sync manager
        self.camera = Camera(sync_manager=self.sync_manager)
        self.gnss = GNSS(sync_manager=self.sync_manager)
        
        # State variables
        self.running = False
        self.recording = False
        self.last_gnss_update = time.time()
        self.show_info = True
    
    def start(self):
        """Start the application"""
        self.logger.info("Starting 360cam_gnss application")
        
        try:
            # Start components in order
            if APP_CONFIG['enable_pps_sync']:
                self.logger.info("Starting PPS synchronization")
                self.sync_manager.start()
                time.sleep(1)  # Allow PPS sync to initialize
            
            self.logger.info("Starting GNSS module")
            self.gnss.start()
            time.sleep(1)  # Allow GNSS to initialize
            
            self.logger.info("Starting camera module")
            self.camera.start()
            
            self.running = True
            
            # Main application loop
            self.main_loop()
            
        except Exception as e:
            self.logger.error(f"Error in application startup: {str(e)}")
            self.stop()
    
    def stop(self):
        """Stop the application"""
        self.logger.info("Stopping 360cam_gnss application")
        
        # Stop recording if active
        if self.recording:
            self.camera.stop_recording()
            self.recording = False
        
        # Stop components in reverse order
        if self.camera:
            self.camera.stop()
        
        if self.gnss:
            self.gnss.stop()
        
        if self.sync_manager:
            self.sync_manager.stop()
        
        self.running = False
        
        self.logger.info("Application stopped")
    
    def signal_handler(self, sig, frame):
        """Handle signals for graceful shutdown"""
        self.logger.info(f"Received signal {sig}, shutting down")
        self.stop()
        sys.exit(0)
    
    def main_loop(self):
        """Main application loop"""
        self.logger.info("Entering main loop")
        
        try:
            while self.running:
                # Get camera preview frame
                if APP_CONFIG['enable_preview'] and self.camera:
                    frame = self.camera.get_preview_frame()
                    
                    if frame is not None:
                        # Add GNSS info overlay
                        if self.show_info:
                            self.add_info_overlay(frame)
                        
                        # Display frame
                        cv2.imshow('360cam GNSS', frame)
                
                # Check for keypress
                key = cv2.waitKey(1) & 0xFF
                
                # Process keypresses
                if key == ord(APP_CONFIG['exit_key']):  # Exit
                    self.logger.info("Exit key pressed, shutting down")
                    break
                elif key == ord('r'):  # Start/stop recording
                    self.toggle_recording()
                elif key == ord('p'):  # Capture photo
                    self.capture_photo()
                elif key == ord('i'):  # Toggle info display
                    self.show_info = not self.show_info
                    self.logger.info(f"Info display: {'on' if self.show_info else 'off'}")
                elif key == ord('w'):  # Add waypoint
                    self.add_waypoint()
                elif key == ord('s'):  # System info
                    self.show_system_info()
                
                # Sleep to reduce CPU usage
                time.sleep(0.01)
        
        except Exception as e:
            self.logger.error(f"Error in main loop: {str(e)}")
        finally:
            self.stop()
            cv2.destroyAllWindows()
    
    def toggle_recording(self):
        """Toggle video recording"""
        if not self.recording:
            self.camera.start_recording()
            self.recording = True
            self.logger.info("Started recording")
        else:
            self.camera.stop_recording()
            self.recording = False
            self.logger.info("Stopped recording")
    
    def capture_photo(self):
        """Capture a photo"""
        photo_path = self.camera.capture_photo()
        if photo_path:
            self.logger.info(f"Captured photo: {photo_path}")
    
    def add_waypoint(self):
        """Add a waypoint at current position"""
        if self.gnss.is_fix_valid():
            name = f"WP_{datetime.now().strftime('%H%M%S')}"
            waypoint = self.gnss.add_waypoint(name)
            if waypoint:
                self.logger.info(f"Added waypoint: {name}")
        else:
            self.logger.warning("Cannot add waypoint: No valid GNSS fix")
    
    def show_system_info(self):
        """Show system information"""
        info = utils.get_system_info()
        self.logger.info(f"System info: {info}")
    
    def add_info_overlay(self, frame):
        """Add information overlay to frame"""
        # Get current time
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add timestamp
        cv2.putText(
            frame,
            current_time,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )
        
        # Add recording status
        if self.recording:
            cv2.putText(
                frame,
                "REC",
                (frame.shape[1] - 80, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )
            
            # Add recording indicator (red circle)
            cv2.circle(
                frame,
                (frame.shape[1] - 100, 25),
                10,
                (0, 0, 255),
                -1
            )
        
        # Add PPS info if available
        if self.sync_manager and APP_CONFIG['enable_pps_sync']:
            pps_time = self.sync_manager.get_last_pps_time()
            pps_count = self.sync_manager.get_pps_count()
            
            if pps_time:
                cv2.putText(
                    frame,
                    f"PPS: {pps_count}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )
        
        # Add GNSS info if available
        if self.gnss:
            position = self.gnss.get_current_position()
            
            if position:
                # Only update every second to keep display readable
                if time.time() - self.last_gnss_update > 1.0:
                    self.last_gnss_update = time.time()
                
                # Format coordinates
                lat_str = f"{position[0]:.6f}°"
                lon_str = f"{position[1]:.6f}°"
                
                # Add to frame
                cv2.putText(
                    frame,
                    f"Lat: {lat_str} Lon: {lon_str}",
                    (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )
                
                # Add altitude if available
                if len(position) > 2 and position[2]:
                    alt_str = f"Alt: {position[2]:.1f}m"
                    cv2.putText(
                        frame,
                        alt_str,
                        (10, 120),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2
                    )
                
                # Add speed and course if available
                speed_course = self.gnss.get_speed_course()
                if speed_course and speed_course['speed']:
                    speed_str = f"Speed: {float(speed_course['speed']) * 1.852:.1f} km/h"  # Convert knots to km/h
                    cv2.putText(
                        frame,
                        speed_str,
                        (10, 150),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2
                    )
                
                # Add fix quality if available
                fix_info = self.gnss.get_fix_info()
                if fix_info:
                    fix_quality = int(fix_info['fix_quality'])
                    num_sats = int(fix_info['num_satellites']) if fix_info['num_satellites'] else 0
                    
                    quality_str = "Fix: "
                    if fix_quality == 0:
                        quality_str += "Invalid"
                        color = (0, 0, 255)  # Red for invalid
                    elif fix_quality == 1:
                        quality_str += "GPS"
                        color = (0, 255, 255)  # Yellow for basic GPS
                    elif fix_quality == 2:
                        quality_str += "DGPS"
                        color = (0, 255, 0)  # Green for DGPS
                    elif fix_quality == 4:
                        quality_str += "RTK"
                        color = (0, 255, 0)  # Green for RTK
                    elif fix_quality == 5:
                        quality_str += "Float RTK"
                        color = (0, 255, 0)  # Green for Float RTK
                    else:
                        quality_str += str(fix_quality)
                        color = (0, 255, 255)  # Yellow for other
                    
                    quality_str += f" ({num_sats} sats)"
                    
                    cv2.putText(
                        frame,
                        quality_str,
                        (10, 180),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        color,
                        2
                    )
        
        # Add help text
        cv2.putText(
            frame,
            "r: record | p: photo | w: waypoint | i: info | s: system | q: quit",
            (10, frame.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )

# Main entry point
if __name__ == "__main__":
    app = MainApplication()
    app.start()
