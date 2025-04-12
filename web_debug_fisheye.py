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
import json
import copy
import threading
from threading import Thread, Event
from datetime import datetime
from camera import Camera
from config import DUAL_FISHEYE_CONFIG, STORAGE_CONFIG, APP_CONFIG
from flask import Flask, render_template, Response, request, jsonify

# Configure logging
logging.basicConfig(
    level=getattr(logging, APP_CONFIG['log_level']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('web_debug_fisheye')

class WebDebugFisheyeCamera(Camera):
    """Web debug class for dual fisheye camera with parameter adjustment via web interface"""
    
    def __init__(self, sync_manager=None):
        """Initialize the WebDebugFisheyeCamera class"""
        # Initialize parent Camera class
        super().__init__(sync_manager)
        
        # Override with fisheye config (create a copy to avoid modifying original)
        self.logger = logging.getLogger('WebDebugFisheyeCamera')
        self.config = copy.deepcopy(DUAL_FISHEYE_CONFIG)
        
        # Display options
        self.display_mode = 'debug'  # Fixed to debug mode
        
        # Debug mode (0: original, 1: equirectangular, 2: debug with both and markers)
        self.debug_mode = 2
        
        # Equirectangular frame
        self.equirectangular_frame = None
        
        # Thread for processing
        self.process_thread = None
        
        # Calibration
        self.fisheye_xmap = None
        self.fisheye_ymap = None
        self.calibration_initialized = False
    
    def update_parameters(self, params):
        """Update parameters from web interface"""
        # Update slider parameters
        for key in ['cx1', 'cy1', 'cx2', 'cy2', 'radius_scale', 'field_of_view', 'fisheye_overlap']:
            if key in params:
                # Convert to proper type
                if key == 'radius_scale':
                    self.config[key] = float(params[key])
                else:
                    self.config[key] = int(params[key])
        
        # Update switch parameters
        for key in ['back_to_back', 'smooth_transition', 'vertical_flip', 'horizontal_flip']:
            if key in params:
                self.config[key] = bool(params[key])
        
        # Reset calibration to force recalculation of maps
        self.calibration_initialized = False
        self.fisheye_xmap = None
        self.fisheye_ymap = None
        
        # Log new parameters
        self.logger.info(f"Updated parameters: CX1={self.config['cx1']}, CY1={self.config['cy1']}, "
                         f"CX2={self.config['cx2']}, CY2={self.config['cy2']}, "
                         f"Radius Scale={self.config['radius_scale']}, "
                         f"FOV={self.config['field_of_view']}°, "
                         f"Overlap={self.config['fisheye_overlap']}°, "
                         f"Back-to-back={self.config['back_to_back']}, "
                         f"Smooth={self.config['smooth_transition']}")
        
        return self.config
    
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
            f.write(f"BACK_TO_BACK = {self.config['back_to_back']}\n")
            f.write(f"SMOOTH_TRANSITION = {self.config['smooth_transition']}\n")
            f.write(f"VERTICAL_FLIP = {self.config['vertical_flip']}\n")
            f.write(f"HORIZONTAL_FLIP = {self.config['horizontal_flip']}\n")
            
            # Add configuration code snippet
            f.write("\n# Configuration for config.py:\n")
            f.write("'''\n")
            f.write("DUAL_FISHEYE_CONFIG = {\n")
            f.write(f"    'cx1': {self.config['cx1']},\n")
            f.write(f"    'cy1': {self.config['cy1']},\n")
            f.write(f"    'cx2': {self.config['cx2']},\n")
            f.write(f"    'cy2': {self.config['cy2']},\n")
            f.write(f"    'radius_scale': {self.config['radius_scale']},\n")
            f.write(f"    'field_of_view': {self.config['field_of_view']},\n")
            f.write(f"    'fisheye_overlap': {self.config['fisheye_overlap']},\n")
            f.write(f"    'back_to_back': {self.config['back_to_back']},\n")
            f.write(f"    'smooth_transition': {self.config['smooth_transition']},\n")
            f.write(f"    'vertical_flip': {self.config['vertical_flip']},\n")
            f.write(f"    'horizontal_flip': {self.config['horizontal_flip']},\n")
            f.write("}\n")
            f.write("'''\n")
        
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
        
        # Flag for 180° opposite direction camera setup
        back_to_back = self.config.get('back_to_back', True)
        
        # Create maps for back-to-back camera setup
        for y in range(equ_h):
            for x in range(equ_w):
                # Convert equirectangular coordinates to spherical
                theta = (x / equ_w) * 2 * np.pi - np.pi  # -pi to pi
                phi = (y / equ_h) * np.pi                # 0 to pi
                
                # Apply vertical flip if needed
                if self.config.get('vertical_flip', False):
                    phi = np.pi - phi
                
                # Apply horizontal flip if needed
                if self.config.get('horizontal_flip', False):
                    theta = -theta
                
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
            
            # Actual blending implementation would be done here
            # This is a placeholder for a more advanced blending algorithm
        
        # Convert maps to correct format for remap
        self.fisheye_xmap = self.fisheye_xmap.astype(np.float32)
        self.fisheye_ymap = self.fisheye_ymap.astype(np.float32)
        
        self.calibration_initialized = True
        self.logger.info(f"Fisheye calibration maps created successfully for {self.config.get('field_of_view')}° camera")
    
    def start(self):
        """Start camera capture"""
        super().start()  # Call parent start method
        
        # Start processing thread
        self.process_thread = Thread(target=self._process_loop)
        self.process_thread.daemon = True
        self.process_thread.start()
    
    def stop(self):
        """Stop camera capture"""
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
                    
                    # Get equirectangular frame
                    self.equirectangular_frame = self.get_equirectangular(self.frame)
                
                # Small delay to match framerate
                time.sleep(0.01)
        
        except Exception as e:
            self.logger.error(f"Process loop error: {str(e)}")
    
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
        equirect_frame = self.equirectangular_frame
        if equirect_frame is None:
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
        
        # Add camera configuration
        back_to_back = "Back-to-back" if self.config.get('back_to_back', True) else "Side-by-side"
        cv2.putText(debug_frame, f"Mode: {back_to_back}, FOV: {self.config.get('field_of_view')}°",
                    (padding, padding + 4*line_height), font, 0.6, (255, 255, 0), 2)
        
        # Create composite view: original frame on top, equirectangular on bottom
        if debug_frame.shape[0] != equirect_frame.shape[0] or debug_frame.shape[1] != equirect_frame.shape[1]:
            equirect_frame = cv2.resize(equirect_frame, (debug_frame.shape[1], debug_frame.shape[0]))
        
        composite = np.vstack((debug_frame, equirect_frame))
        
        # Add labels
        label_y_pos = debug_frame.shape[0] - padding
        cv2.putText(composite, "Original with Center Points", 
                    (padding, label_y_pos), font, 0.8, (255, 255, 255), 2)
        cv2.putText(composite, "Equirectangular Conversion", 
                    (padding, label_y_pos + debug_frame.shape[0] + line_height), font, 0.8, (255, 255, 255), 2)
        
        return composite
    
    def get_preview_frame(self):
        """Get a frame for preview with selected debug mode"""
        if self.frame is None:
            return None
            
        if self.debug_mode == 0:
            # Original frame
            return self.frame.copy()
        elif self.debug_mode == 1:
            # Equirectangular only
            if self.equirectangular_frame is not None:
                return self.equirectangular_frame.copy()
            else:
                return self.frame.copy()
        else:
            # Debug view with both frames and markers
            return self.get_debug_view(self.frame)

# Global variables
camera = None
recording = False
preview_thread = None
stop_preview = False
last_frame = None
frame_lock = threading.Lock()

# Create Flask app
app = Flask(__name__)

# Create templates directory if it doesn't exist
os.makedirs('templates', exist_ok=True)

# Function to convert OpenCV frame to jpeg
def convert_frame_to_jpeg(frame):
    if frame is None:
        return None
    
    # Resize for preview if needed to fit web view
    frame_height, frame_width = frame.shape[:2]
    max_width = 1024
    
    if frame_width > max_width:
        scale = max_width / frame_width
        new_width = int(frame_width * scale)
        new_height = int(frame_height * scale)
        frame = cv2.resize(frame, (new_width, new_height))
    
    # Convert to jpeg
    _, buffer = cv2.imencode('.jpg', frame)
    return buffer.tobytes()

# Preview update thread
def update_preview():
    global stop_preview, last_frame
    
    while not stop_preview:
        if camera and camera.running:
            frame = camera.get_preview_frame()
            
            if frame is not None:
                with frame_lock:
                    last_frame = convert_frame_to_jpeg(frame)
        
        time.sleep(0.1)  # Update at ~10 FPS to reduce CPU load

# Generate camera frames for streaming
def generate_frames():
    global last_frame
    
    while True:
        with frame_lock:
            if last_frame is not None:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + last_frame + b'\r\n')
        
        time.sleep(0.1)

# Routes
@app.route('/')
def index():
    return render_template('debug_fisheye_index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/start_camera', methods=['POST'])
def start_camera():
    global camera, preview_thread, stop_preview
    
    if camera is None:
        camera = WebDebugFisheyeCamera()
    
    if not camera.running:
        if camera.open():
            camera.start()
            
            # Start preview thread
            stop_preview = False
            preview_thread = threading.Thread(target=update_preview)
            preview_thread.daemon = True
            preview_thread.start()
            
            return jsonify({"status": "success", "message": "カメラを起動しました"})
        else:
            return jsonify({"status": "error", "message": "カメラの初期化に失敗しました"})
    else:
        return jsonify({"status": "info", "message": "カメラは既に起動しています"})

@app.route('/api/stop_camera', methods=['POST'])
def stop_camera():
    global camera, stop_preview, recording
    
    if camera and camera.running:
        # Stop recording if active
        if recording:
            camera.stop_recording()
            recording = False
        
        # Stop preview thread
        stop_preview = True
        if preview_thread:
            preview_thread.join(timeout=1.0)
        
        # Stop camera
        camera.stop()
        
        return jsonify({"status": "success", "message": "カメラを停止しました"})
    else:
        return jsonify({"status": "info", "message": "カメラは既に停止しています"})

@app.route('/api/toggle_recording', methods=['POST'])
def toggle_recording():
    global camera, recording
    
    if camera and camera.running:
        if not recording:
            # Start recording
            camera.start_recording()
            recording = True
            return jsonify({"status": "success", "message": "録画を開始しました", "recording": True})
        else:
            # Stop recording
            camera.stop_recording()
            recording = False
            video_path = camera.current_video_path if camera.current_video_path else "不明"
            return jsonify({"status": "success", "message": f"録画を停止しました: {video_path}", "recording": False})
    else:
        return jsonify({"status": "error", "message": "カメラが起動していません"})

@app.route('/api/capture_photo', methods=['POST'])
def capture_photo():
    global camera
    
    if camera and camera.running:
        photo_path = camera.capture_photo()
        
        if photo_path:
            return jsonify({"status": "success", "message": f"写真を保存しました: {photo_path}"})
        else:
            return jsonify({"status": "error", "message": "写真の撮影に失敗しました"})
    else:
        return jsonify({"status": "error", "message": "カメラが起動していません"})

@app.route('/api/update_parameters', methods=['POST'])
def update_parameters():
    global camera
    
    if camera and camera.running:
        # Get parameters from request
        params = request.json
        
        # Update camera parameters
        updated_params = camera.update_parameters(params)
        
        return jsonify({
            "status": "success", 
            "message": "パラメータを更新しました", 
            "parameters": updated_params
        })
    else:
        return jsonify({"status": "error", "message": "カメラが起動していません"})

@app.route('/api/save_parameters', methods=['POST'])
def save_parameters():
    global camera
    
    if camera and camera.running:
        # Save current parameters to file
        filename = camera.save_current_parameters()
        
        return jsonify({
            "status": "success", 
            "message": f"パラメータを保存しました: {filename}"
        })
    else:
        return jsonify({"status": "error", "message": "カメラが起動していません"})

@app.route('/api/set_debug_mode', methods=['POST'])
def set_debug_mode():
    global camera
    
    if camera and camera.running:
        # Get debug mode from request
        mode = request.json.get('mode', 2)  # Default to debug composite view
        
        # Update debug mode
        camera.debug_mode = int(mode)
        
        mode_names = ["元映像", "全天球変換", "デバッグビュー"]
        mode_name = mode_names[camera.debug_mode] if 0 <= camera.debug_mode < len(mode_names) else "不明"
        
        return jsonify({
            "status": "success", 
            "message": f"表示モードを切り替えました: {mode_name}", 
            "mode": camera.debug_mode
        })
    else:
        return jsonify({"status": "error", "message": "カメラが起動していません"})

@app.route('/api/status', methods=['GET'])
def get_status():
    global camera, recording
    
    camera_status = "running" if camera and camera.running else "stopped"
    recording_status = recording
    
    parameters = {}
    debug_mode = 2
    
    if camera and camera.running:
        # Get current parameters
        parameters = {
            'cx1': camera.config.get('cx1', 360),
            'cy1': camera.config.get('cy1', 360),
            'cx2': camera.config.get('cx2', 1080),
            'cy2': camera.config.get('cy2', 360),
            'radius_scale': camera.config.get('radius_scale', 1.2),
            'field_of_view': camera.config.get('field_of_view', 220),
            'fisheye_overlap': camera.config.get('fisheye_overlap', 10),
            'back_to_back': camera.config.get('back_to_back', True),
            'smooth_transition': camera.config.get('smooth_transition', True),
            'vertical_flip': camera.config.get('vertical_flip', False),
            'horizontal_flip': camera.config.get('horizontal_flip', False)
        }
        debug_mode = camera.debug_mode
    
    return jsonify({
        "camera": camera_status,
        "recording": recording_status,
        "debug_mode": debug_mode,
        "parameters": parameters
    })

# Main function
def main():
    app.run(host='0.0.0.0', port=8082, debug=True)

if __name__ == '__main__':
    main()
