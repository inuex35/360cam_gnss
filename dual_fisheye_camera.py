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
import subprocess
from datetime import datetime
from threading import Thread, Event
import numpy as np

from camera import Camera
from config import DUAL_FISHEYE_CONFIG, STORAGE_CONFIG, APP_CONFIG

class DualFisheyeCamera(Camera):
    """Class for managing dual fisheye camera with real-time equirectangular conversion and streaming"""
    
    def __init__(self, sync_manager=None):
        """
        Initialize the DualFisheyeCamera class
        
        Args:
            sync_manager: Instance of sync manager (optional)
        """
        # Initialize parent Camera class
        super().__init__(sync_manager)
        
        # Override with fisheye config
        self.logger = logging.getLogger('DualFisheyeCamera')
        self.config = DUAL_FISHEYE_CONFIG
        
        # Display options - override parent class
        self.display_mode = self.config.get('display_mode', 'equirectangular')  # 'fisheye', 'equirectangular'
        
        # Equirectangular frame
        self.equirectangular_frame = None
        
        # Process thread for equirectangular conversion
        self.process_thread = None
        
        # Calibration
        self.init_calibration()
    
    def init_calibration(self):
        """Initialize calibration parameters for equirectangular conversion"""
        self.logger.info("Initializing dual fisheye calibration parameters")
        
        # Get calibration parameters from config
        self.fisheye_xmap = None
        self.fisheye_ymap = None
        
        # Lazy initialization - will be built the first time it's needed
        self.calibration_initialized = False
    
    def _create_fisheye_maps(self):
        """Create mapping for fisheye to equirectangular conversion - optimized for back-to-back 180° camera setup"""
        # Only create maps if not already initialized
        if self.calibration_initialized:
            return
            
        # Get frame dimensions
        width = self.config['width']
        height = self.config['height']
        
        # Create maps
        self.logger.info(f"Creating fisheye mapping with dimensions {width}x{height} for back-to-back {self.config.get('field_of_view', 220)}° camera")
        
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
        
        # Flag for 180° opposite direction camera setup
        back_to_back = self.config.get('back_to_back', True)
        
        # Create maps for back-to-back camera setup
        for y in range(equ_h):
            for x in range(equ_w):
                # Convert equirectangular coordinates to spherical
                theta = (x / equ_w) * 2 * np.pi - np.pi  # -pi to pi
                phi = (y / equ_h) * np.pi                # 0 to pi
                
                # Convert spherical to 3D Cartesian
                x3d = np.sin(phi) * np.cos(theta)
                y3d = np.sin(phi) * np.sin(theta)
                z3d = np.cos(phi)
                
                # Back-to-back cameras (opposite directions)
                if back_to_back:
                    # Use the appropriate fisheye lens based on the horizontal angle (theta)
                    # Front hemisphere: -π/2 to π/2
                    # Rear hemisphere: π/2 to 3π/2 (or -3π/2 to -π/2)
                    if -np.pi/2 <= theta <= np.pi/2:
                        # Front fisheye (first camera)
                        # Project 3D point to fisheye image
                        r = radius * np.sqrt(x3d*x3d + z3d*z3d) / (y3d + 1e-6)
                        angle = np.arctan2(z3d, x3d)
                        
                        # Scale for field of view
                        scale_factor = max_theta / (np.pi/2)  # Adjust scaling for FOV
                        r = r / scale_factor
                        
                        # Map to image coordinates
                        self.fisheye_xmap[y, x] = cx1 + r * np.cos(angle)
                        self.fisheye_ymap[y, x] = cy1 + r * np.sin(angle)
                    else:
                        # Rear fisheye (second camera)
                        # For back-to-back cameras, we need to flip the direction
                        # Since the second camera is facing the opposite direction
                        theta_adjusted = theta - np.pi if theta > 0 else theta + np.pi
                        
                        # Recalculate 3D position for the rear camera
                        x3d_rear = np.sin(phi) * np.cos(theta_adjusted)
                        y3d_rear = np.sin(phi) * np.sin(theta_adjusted)
                        z3d_rear = np.cos(phi)
                        
                        # Project to fisheye coordinates
                        r = radius * np.sqrt(x3d_rear*x3d_rear + z3d_rear*z3d_rear) / (y3d_rear + 1e-6)
                        angle = np.arctan2(z3d_rear, x3d_rear)
                        
                        # Scale for field of view
                        scale_factor = max_theta / (np.pi/2)
                        r = r / scale_factor
                        
                        # Map to image coordinates (second camera)
                        self.fisheye_xmap[y, x] = cx2 + r * np.cos(angle)
                        self.fisheye_ymap[y, x] = cy2 + r * np.sin(angle)
                else:
                    # Original approach for side-by-side (not back-to-back) cameras
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
        
        # Optionally apply smoothing to the transition regions
        if self.config.get('smooth_transition', True) and back_to_back:
            blend_width = int(equ_w * 0.05)  # 5% of width for blending on each side
            front_back_boundary1 = int(equ_w * 0.25)  # Around -π/2
            front_back_boundary2 = int(equ_w * 0.75)  # Around π/2
            
            for y in range(equ_h):
                # Blend region around -π/2
                for x in range(front_back_boundary1 - blend_width, front_back_boundary1 + blend_width):
                    if 0 <= x < equ_w:
                        blend_factor = 0.5 + 0.5 * np.sin(np.pi * (x - (front_back_boundary1 - blend_width)) / (2 * blend_width) - np.pi/2)
                        # Create a weighted average of the mapping in the blend region
                        # This would require pre-calculating both mappings
                
                # Blend region around π/2
                for x in range(front_back_boundary2 - blend_width, front_back_boundary2 + blend_width):
                    if 0 <= x < equ_w:
                        blend_factor = 0.5 + 0.5 * np.sin(np.pi * (x - (front_back_boundary2 - blend_width)) / (2 * blend_width) - np.pi/2)
                        # Create a weighted average of the mapping in the blend region
        
        # Convert maps to correct format for remap
        self.fisheye_xmap = self.fisheye_xmap.astype(np.float32)
        self.fisheye_ymap = self.fisheye_ymap.astype(np.float32)
        
        self.calibration_initialized = True
        self.logger.info(f"Fisheye calibration maps created successfully for {self.config.get('field_of_view')}° camera")
    
    def start(self):
        """Start camera capture - override parent method"""
        super().start()  # Call parent start method
        
        # Start additional processing thread for equirectangular conversion
        if self.running:
            self.process_thread = Thread(target=self._process_loop)
            self.process_thread.daemon = True
            self.process_thread.start()
    
    def stop(self):
        """Stop camera capture - override parent method"""
        self.stop_event.set()
        
        if self.process_thread:
            self.process_thread.join(timeout=3.0)
            
        super().stop()  # Call parent stop method
    
    def _process_loop(self):
        """Process captured frames for equirectangular conversion"""
        try:
            while not self.stop_event.is_set():
                if self.frame is not None:
                    # Convert to equirectangular if needed
                    if not self.calibration_initialized:
                        self._create_fisheye_maps()
                    
                    # Apply equirectangular conversion
                    self.equirectangular_frame = self._convert_to_equirectangular(self.frame)
                
                # Small delay to match framerate
                time.sleep(0.01)
        
        except Exception as e:
            self.logger.error(f"Process loop error: {str(e)}")
    
    def _convert_to_equirectangular(self, frame):
        """Convert dual fisheye frame to equirectangular projection"""
        if frame is None:
            return None
        
        try:
            # Get equirectangular dimensions
            equ_h = int(frame.shape[0] * self.config.get('equ_height_ratio', 0.5))
            equ_w = frame.shape[1]
            
            # Remap using the pre-calculated maps
            equirectangular = cv2.remap(frame, self.fisheye_xmap, self.fisheye_ymap, 
                                        cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            
            return equirectangular
        except Exception as e:
            self.logger.error(f"Equirectangular conversion error: {str(e)}")
            return frame
    
    def get_preview_frame(self):
        """Get a frame for preview - override parent method"""
        if self.display_mode == 'equirectangular' and self.equirectangular_frame is not None:
            frame = self.equirectangular_frame
        else:
            # Use parent class method to get frame
            frame = super().get_preview_frame()
        
        if frame is None:
            return None
            
        try:
            # Resize if needed
            if self.config['preview_width'] > 0 and self.config['preview_height'] > 0:
                frame = cv2.resize(frame, (self.config['preview_width'], self.config['preview_height']))
                
            return frame
        except Exception as e:
            self.logger.error(f"Preview frame error: {str(e)}")
            return None
    
    def set_display_mode(self, mode):
        """Set the display mode - override parent method"""
        valid_modes = ['fisheye', 'equirectangular']
        
        if mode in valid_modes:
            self.display_mode = mode
            self.logger.info(f"Display mode set to: {mode}")
            return True
        else:
            self.logger.warning(f"Invalid display mode: {mode}. Valid modes are: {valid_modes}")
            return False
    
    def toggle_display_mode(self):
        """Toggle between available display modes - override parent method"""
        modes = ['fisheye', 'equirectangular']
        current_index = modes.index(self.display_mode) if self.display_mode in modes else 0
        next_index = (current_index + 1) % len(modes)
        self.display_mode = modes[next_index]
        self.logger.info(f"Display mode toggled to: {self.display_mode}")
        return self.display_mode
    
    def capture_photo(self):
        """Capture a photo - override parent method"""
        if not self.running:
            self.logger.warning("Camera not started")
            return None
        
        try:
            timestamp = datetime.now().strftime(self.storage_config['timestamp_format'])
            
            if self.storage_config['use_timestamp_subdir']:
                subdir = datetime.now().strftime("%Y%m%d")
                photo_dir = os.path.join(
                    self.storage_config['base_path'],
                    self.storage_config['photo_dir'],
                    subdir
                )
                if not os.path.exists(photo_dir):
                    os.makedirs(photo_dir)
            else:
                photo_dir = os.path.join(
                    self.storage_config['base_path'],
                    self.storage_config['photo_dir']
                )
            
            # Determine which frame to save based on display mode
            if self.display_mode == 'equirectangular' and self.equirectangular_frame is not None:
                # Save equirectangular photo
                photo_filename = f"equirectangular_{timestamp}{self.config['photo_extension']}"
                photo_path = os.path.join(photo_dir, photo_filename)
                cv2.imwrite(photo_path, self.equirectangular_frame)
            else:
                # Use parent class method to capture photo
                return super().capture_photo()
            
            self.logger.info(f"Saved photo: {photo_path}")
            
            # Notify sync manager of photo capture
            if self.sync_manager:
                self.sync_manager.register_photo_capture(photo_path, datetime.now())
            
            return photo_path
        except Exception as e:
            self.logger.error(f"Photo capture error: {str(e)}")
            return None
