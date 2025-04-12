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
import os
import logging
import sys
import numpy as np
from threading import Thread, Event
from datetime import datetime
from camera import Camera
from config import DUAL_FISHEYE_CONFIG, STORAGE_CONFIG, APP_CONFIG
import copy

# Configure logging
logging.basicConfig(
    level=getattr(logging, APP_CONFIG['log_level']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('debug_dual_fisheye')

class DebugDualFisheyeCamera(Camera):
    """Debug class for dual fisheye camera with parameter adjustment GUI"""
    
    def __init__(self, sync_manager=None):
        """Initialize the DebugDualFisheyeCamera class"""
        # Initialize parent Camera class
        super().__init__(sync_manager)
        
        # Override with fisheye config (create a copy to avoid modifying original)
        self.logger = logging.getLogger('DebugDualFisheyeCamera')
        self.config = copy.deepcopy(DUAL_FISHEYE_CONFIG)
        
        # Display options
        self.display_mode = 'debug'  # Fixed to debug mode
        
        # Equirectangular frame
        self.equirectangular_frame = None
        
        # Parameter adjustment trackbars
        self.trackbar_window_name = 'Fisheye Parameters'
        self.create_parameter_window()
        
        # Calibration
        self.fisheye_xmap = None
        self.fisheye_ymap = None
        self.calibration_initialized = False
    
    def create_parameter_window(self):
        """Create window with trackbars for adjusting parameters"""
        cv2.namedWindow(self.trackbar_window_name)
        
        # Center positions
        cv2.createTrackbar('CX1', self.trackbar_window_name, self.config.get('cx1', 360), 
                           self.config.get('width', 1440), self.update_parameter)
        cv2.createTrackbar('CY1', self.trackbar_window_name, self.config.get('cy1', 360), 
                           self.config.get('height', 720), self.update_parameter)
        cv2.createTrackbar('CX2', self.trackbar_window_name, self.config.get('cx2', 1080), 
                           self.config.get('width', 1440), self.update_parameter)
        cv2.createTrackbar('CY2', self.trackbar_window_name, self.config.get('cy2', 360), 
                           self.config.get('height', 720), self.update_parameter)
        
        # Radius scale (0.1 to 2.0 - multiplied by 100 for trackbar)
        radius_scale = int(self.config.get('radius_scale', 0.9) * 100)
        cv2.createTrackbar('Radius Scale (%)', self.trackbar_window_name, radius_scale, 200, self.update_parameter)
        
        # Field of view (100 to 240 degrees)
        cv2.createTrackbar('Field of View (°)', self.trackbar_window_name, 
                          self.config.get('field_of_view', 220), 240, self.update_parameter)
        
        # Overlap (0 to 30 degrees)
        cv2.createTrackbar('Overlap (°)', self.trackbar_window_name, 
                          self.config.get('fisheye_overlap', 10), 30, self.update_parameter)
    
    def update_parameter(self, value):
        """Callback when trackbar is adjusted"""
        # Get current values from trackbars
        self.config['cx1'] = cv2.getTrackbarPos('CX1', self.trackbar_window_name)
        self.config['cy1'] = cv2.getTrackbarPos('CY1', self.trackbar_window_name)
        self.config['cx2'] = cv2.getTrackbarPos('CX2', self.trackbar_window_name)
        self.config['cy2'] = cv2.getTrackbarPos('CY2', self.trackbar_window_name)
        
        # Convert radius scale from percentage to float
        radius_scale_percent = cv2.getTrackbarPos('Radius Scale (%)', self.trackbar_window_name)
        self.config['radius_scale'] = radius_scale_percent / 100.0
        
        self.config['field_of_view'] = cv2.getTrackbarPos('Field of View (°)', self.trackbar_window_name)
        self.config['fisheye_overlap'] = cv2.getTrackbarPos('Overlap (°)', self.trackbar_window_name)
        
        # Reset calibration to force recalculation of maps
        self.calibration_initialized = False
        self.fisheye_xmap = None
        self.fisheye_ymap = None
        
        # Log new parameters
        self.logger.info(f"Updated parameters: CX1={self.config['cx1']}, CY1={self.config['cy1']}, "
                         f"CX2={self.config['cx2']}, CY2={self.config['cy2']}, "
                         f"Radius Scale={self.config['radius_scale']}, "
                         f"FOV={self.config['field_of_view']}°, "
                         f"Overlap={self.config['fisheye_overlap']}°")
    
    def save_current_parameters(self):
        """Save current parameters to a file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fisheye_params_{timestamp}.txt"
        
        with open(filename, 'w') as f:
            f.write("# Dual Fisheye Parameters\n")
            f.write(f"CX1 = {self.config['cx1']}\n")
            f.write(f"CY1 = {self.config['cy1']}\n")
            f.write(f"CX2 = {self.config['cx2']}\n")
            f.write(f"CY2 = {self.config['cy2']}\n")
            f.write(f"RADIUS_SCALE = {self.config['radius_scale']}\n")
            f.write(f"FIELD_OF_VIEW = {self.config['field_of_view']}\n")
            f.write(f"OVERLAP = {self.config['fisheye_overlap']}\n")
        
        self.logger.info(f"Parameters saved to {filename}")
        return filename
    
    def _create_fisheye_maps(self):
        """Create mapping for fisheye to equirectangular conversion"""
        # Only create maps if not already initialized
        if self.calibration_initialized:
            return
            
        # Get frame dimensions
        width = self.config['width']
        height = self.config['height']
        
        # Create maps
        self.logger.info(f"Creating fisheye mapping with dimensions {width}x{height} "
                         f"for {self.config.get('field_of_view')}° camera")
        
        # Create destination map
        equ_h = int(height * self.config.get('equ_height_ratio', 0.5))
        equ_w = width
        
        # Create empty maps for x and y coordinate mappings
        self.fisheye_xmap = np.zeros((equ_h, equ_w), np.float32)
        self.fisheye_ymap = np.zeros((equ_h, equ_w), np.float32)
        
        # Calculate center point for each fisheye lens
        cx1 = self.config.get('cx1')  # Left fisheye center x
        cy1 = self.config.get('cy1')  # Left fisheye center y
        cx2 = self.config.get('cx2')  # Right fisheye center x
        cy2 = self.config.get('cy2')  # Right fisheye center y
        
        # Calculate radius for fisheye lens
        radius = min(cx1, cy1) if cx1 < cx2 else min(width - cx2, cy2)
        radius = int(radius * self.config.get('radius_scale'))
        
        # Get field of view and overlap parameters
        fov = np.radians(self.config.get('field_of_view'))  # Camera FOV in radians
        overlap = np.radians(self.config.get('fisheye_overlap'))  # Overlap region in radians
        
        # Calculate maximum theta angle based on field of view
        max_theta = fov / 2
        
        # Create maps with simplified approach
        for y in range(equ_h):
            for x in range(equ_w):
                # Convert equirectangular coordinates to spherical
                theta = (x / equ_w) * 2 * np.pi - np.pi  # -pi to pi
                phi = (y / equ_h) * np.pi                # 0 to pi
                
                # Convert spherical to 3D Cartesian
                x3d = np.sin(phi) * np.cos(theta)
                y3d = np.sin(phi) * np.sin(theta)
                z3d = np.cos(phi)
                
                # Simplified approach: use left half for left hemisphere, right half for right hemisphere
                if theta < 0:  # Left hemisphere
                    # Calculate fisheye projection parameters
                    r = radius * np.sqrt(x3d*x3d + z3d*z3d) / (y3d + 1e-6)
                    angle = np.arctan2(z3d, x3d)
                    
                    # Scale for field of view
                    scale_factor = max_theta / (np.pi/2)  # Adjust scaling for FOV
                    r = r / scale_factor
                    
                    # Map to coordinates
                    self.fisheye_xmap[y, x] = cx1 + r * np.cos(angle)
                    self.fisheye_ymap[y, x] = cy1 + r * np.sin(angle)
                else:  # Right hemisphere
                    # Calculate fisheye projection parameters
                    r = radius * np.sqrt(x3d*x3d + z3d*z3d) / (y3d + 1e-6)
                    angle = np.arctan2(z3d, x3d)
                    
                    # Scale for field of view
                    scale_factor = max_theta / (np.pi/2)
                    r = r / scale_factor
                    
                    # Map to coordinates
                    self.fisheye_xmap[y, x] = cx2 + r * np.cos(angle)
                    self.fisheye_ymap[y, x] = cy2 + r * np.sin(angle)
        
        # Convert maps to correct format for remap
        self.fisheye_xmap = self.fisheye_xmap.astype(np.float32)
        self.fisheye_ymap = self.fisheye_ymap.astype(np.float32)
        
        self.calibration_initialized = True
        self.logger.info(f"Fisheye calibration maps created successfully for {self.config.get('field_of_view')}° camera")
    
    def start(self):
        """Start camera capture"""
        super().start()  # Call parent start method
    
    def stop(self):
        """Stop camera capture"""
        cv2.destroyWindow(self.trackbar_window_name)
        super().stop()  # Call parent stop method
    
    def get_equirectangular(self, frame):
        """Convert frame to equirectangular projection"""
        if frame is None:
            return None
        
        try:
            # Create calibration maps if needed
            if not self.calibration_initialized:
                self._create_fisheye_maps()
            
            # Get equirectangular dimensions
            equ_h = int(frame.shape[0] * self.config.get('equ_height_ratio', 0.5))
            equ_w = frame.shape[1]
            
            # Remap using the pre-calculated maps
            equirectangular = cv2.remap(frame, self.fisheye_xmap, self.fisheye_ymap, 
                                        cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            
            return equirectangular
        except Exception as e:
            self.logger.error(f"Equirectangular conversion error: {str(e)}")
            return None
    
    def get_debug_view(self, frame):
        """Create debug view showing original and converted images"""
        if frame is None:
            return None
        
        # Get equirectangular projection
        equirectangular = self.get_equirectangular(frame)
        if equirectangular is None:
            return frame
        
        # Draw center points and radius on original frame
        debug_frame = frame.copy()
        cx1 = self.config.get('cx1')
        cy1 = self.config.get('cy1')
        cx2 = self.config.get('cx2')
        cy2 = self.config.get('cy2')
        
        # Calculate radius
        radius = min(cx1, cy1) if cx1 < cx2 else min(debug_frame.shape[1] - cx2, cy2)
        radius = int(radius * self.config.get('radius_scale'))
        
        # Draw circles at center points and radius
        cv2.circle(debug_frame, (cx1, cy1), 5, (0, 0, 255), -1)  # Red dot for center 1
        cv2.circle(debug_frame, (cx2, cy2), 5, (0, 0, 255), -1)  # Red dot for center 2
        cv2.circle(debug_frame, (cx1, cy1), radius, (0, 255, 0), 2)  # Green circle for radius 1
        cv2.circle(debug_frame, (cx2, cy2), radius, (0, 255, 0), 2)  # Green circle for radius 2
        
        # Add parameter text
        font = cv2.FONT_HERSHEY_SIMPLEX
        line_height = 25
        padding = 10
        
        # Parameters on original frame
        cv2.putText(debug_frame, f"CX1: {cx1}, CY1: {cy1}", 
                    (padding, padding + line_height), font, 0.6, (255, 255, 0), 2)
        cv2.putText(debug_frame, f"CX2: {cx2}, CY2: {cy2}", 
                    (padding, padding + 2*line_height), font, 0.6, (255, 255, 0), 2)
        cv2.putText(debug_frame, f"Radius Scale: {self.config.get('radius_scale'):.2f}", 
                    (padding, padding + 3*line_height), font, 0.6, (255, 255, 0), 2)
        cv2.putText(debug_frame, f"FOV: {self.config.get('field_of_view')}°, Overlap: {self.config.get('fisheye_overlap')}°", 
                    (padding, padding + 4*line_height), font, 0.6, (255, 255, 0), 2)
        
        # Create composite view: original frame on top, equirectangular on bottom
        if debug_frame.shape[0] != equirectangular.shape[0] or debug_frame.shape[1] != equirectangular.shape[1]:
            equirectangular = cv2.resize(equirectangular, (debug_frame.shape[1], debug_frame.shape[0]))
        
        composite = np.vstack((debug_frame, equirectangular))
        
        # Add labels
        label_y_pos = debug_frame.shape[0] - padding
        cv2.putText(composite, "Original with Center Points", 
                    (padding, label_y_pos), font, 0.8, (255, 255, 255), 2)
        cv2.putText(composite, "Equirectangular Conversion", 
                    (padding, label_y_pos + debug_frame.shape[0] + line_height), font, 0.8, (255, 255, 255), 2)
        
        return composite
    
    def get_preview_frame(self):
        """Get a frame for preview with debug information"""
        if self.frame is None:
            return None
        
        # Create debug view
        composite = self.get_debug_view(self.frame)
        
        # Resize if needed
        if composite is not None and self.config['preview_width'] > 0 and self.config['preview_height'] > 0:
            aspect_ratio = composite.shape[1] / composite.shape[0]
            preview_height = int(self.config['preview_width'] / aspect_ratio)
            composite = cv2.resize(composite, (self.config['preview_width'], preview_height))
        
        return composite

# Main function
def main():
    logger.info("Starting debug dual fisheye camera mode")
    
    # Create camera instance
    camera = DebugDualFisheyeCamera()
    
    try:
        # Initialize camera
        if not camera.open():
            logger.error("Failed to initialize camera")
            return
        
        # Start camera
        camera.start()
        logger.info("Camera started in debug mode")
        logger.info("Press 's' to save parameters, 'q' to quit")
        
        while True:
            # Get debug frame
            frame = camera.get_preview_frame()
            
            if frame is not None:
                # Display frame
                cv2.imshow('Debug Dual Fisheye Camera', frame)
            
            # Check for keyboard input
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                # Quit
                logger.info("Quitting...")
                break
            
            elif key == ord('s'):
                # Save parameters
                param_file = camera.save_current_parameters()
                logger.info(f"Parameters saved to {param_file}")
                
                # Display save notification on the frame
                if frame is not None:
                    notification_frame = frame.copy()
                    cv2.putText(notification_frame, f"Parameters saved to {param_file}", 
                                (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.imshow('Debug Dual Fisheye Camera', notification_frame)
                    cv2.waitKey(1000)  # Show notification for 1 second
    
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    
    finally:
        # Stop camera
        camera.stop()
        cv2.destroyAllWindows()
        logger.info("Camera stopped")

# Entry point
if __name__ == "__main__":
    main()
