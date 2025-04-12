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
import logging
import sys
import os
from dual_fisheye_camera import DualFisheyeCamera
from config import APP_CONFIG

# Configure logging
logging.basicConfig(
    level=getattr(logging, APP_CONFIG['log_level']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('start_dual_fisheye')

# Main function
def main():
    logger.info("Starting dual fisheye camera in command-line mode")
    
    # Create camera instance
    camera = DualFisheyeCamera()
    
    try:
        # Initialize camera
        if not camera.open():
            logger.error("Failed to initialize camera")
            return
        
        # Start camera
        camera.start()
        logger.info("Camera started")
        logger.info("Press 'r' to start/stop recording, 'd' to toggle display mode, 'p' to take a photo, 'q' to quit")
        
        while True:
            # Get preview frame
            frame = camera.get_preview_frame()
            
            if frame is not None:
                # Display frame
                cv2.imshow('Dual Fisheye Camera', frame)
            
            # Check for keyboard input
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                # Quit
                logger.info("Quitting...")
                break
                
            elif key == ord('r'):
                # Toggle recording
                if camera.recording:
                    camera.stop_recording()
                    logger.info("Recording stopped")
                else:
                    camera.start_recording()
                    logger.info("Recording started")
                    
            elif key == ord('d'):
                # Toggle display mode
                new_mode = camera.toggle_display_mode()
                logger.info(f"Display mode set to: {new_mode}")
                
            elif key == ord('p'):
                # Capture photo
                photo_path = camera.capture_photo()
                if photo_path:
                    logger.info(f"Photo saved: {photo_path}")
                else:
                    logger.error("Failed to capture photo")
    
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    
    finally:
        # Stop camera
        if camera.recording:
            camera.stop_recording()
        
        camera.stop()
        cv2.destroyAllWindows()
        logger.info("Camera stopped")

# Entry point
if __name__ == "__main__":
    main()
