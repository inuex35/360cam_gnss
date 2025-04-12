#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Flask-based web app for controlling the dual fisheye 360 camera on Raspberry Pi
# Compatible with Python 3.7

import os
import time
import threading
import base64
import io
import cv2
import numpy as np
from datetime import datetime
from flask import Flask, render_template, Response, request, jsonify
from dual_fisheye_camera import DualFisheyeCamera

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
    
    # Resize for preview if needed
    frame = cv2.resize(frame, (800, 400))
    
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
    return render_template('dual_fisheye_index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/start_camera', methods=['POST'])
def start_camera():
    global camera, preview_thread, stop_preview
    
    if camera is None:
        camera = DualFisheyeCamera()
    
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

@app.route('/api/toggle_display_mode', methods=['POST'])
def toggle_display_mode():
    global camera
    
    if camera and camera.running:
        new_mode = camera.toggle_display_mode()
        mode_names = {
            'fisheye': 'デュアルフィッシュアイ',
            'equirectangular': '全天球展開'
        }
        mode_text = mode_names.get(new_mode, new_mode)
        
        return jsonify({"status": "success", "message": f"表示モードを切り替えました: {mode_text}", "mode": new_mode})
    else:
        return jsonify({"status": "error", "message": "カメラが起動していません"})

@app.route('/api/status', methods=['GET'])
def get_status():
    global camera, recording
    
    camera_status = "running" if camera and camera.running else "stopped"
    recording_status = recording
    
    if camera and camera.running:
        display_mode = camera.display_mode
    else:
        display_mode = "equirectangular"
    
    return jsonify({
        "camera": camera_status,
        "recording": recording_status,
        "display_mode": display_mode
    })

# Create HTML template
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>360° デュアルフィッシュアイカメラコントロール</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            margin-bottom: 20px;
        }
        .status {
            display: flex;
            margin-bottom: 10px;
        }
        .status-item {
            margin-right: 20px;
            padding: 5px;
            border-radius: 4px;
        }
        .preview {
            border: 2px solid #444;
            border-radius: 8px;
            background-color: #000;
            padding: 10px;
            text-align: center;
            margin-bottom: 20px;
        }
        .preview img {
            max-width: 100%;
            height: auto;
            border-radius: 4px;
        }
        .controls {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 10px;
            margin-bottom: 20px;
        }
        button {
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            min-width: 120px;
        }
        .btn-start {
            background-color: #4CAF50;
            color: white;
        }
        .btn-stop {
            background-color: #f44336;
            color: white;
        }
        .btn-record {
            background-color: #f44336;
            color: white;
        }
        .btn-photo {
            background-color: #2196F3;
            color: white;
        }
        .btn-mode {
            background-color: #9C27B0;
            color: white;
        }
        .status-box {
            margin-top: 20px;
            border: 1px solid #ddd;
            padding: 10px;
            border-radius: 4px;
            background-color: #fff;
        }
        .notification {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 10px 20px;
            background-color: #333;
            color: white;
            border-radius: 4px;
            display: none;
            max-width: 300px;
        }
        .disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        @media (max-width: 600px) {
            .controls {
                flex-direction: column;
            }
            button {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>360° デュアルフィッシュアイカメラコントロール</h1>
        
        <div class="status">
            <div class="status-item" id="camera-status">カメラ: 停止中</div>
            <div class="status-item" id="recording-status">録画: 停止中</div>
        </div>
        
        <div class="preview">
            <img id="camera-preview" src="/video_feed" alt="カメラプレビュー">
        </div>
        
        <div class="controls">
            <button id="btn-start-camera" class="btn-start">カメラ起動</button>
            <button id="btn-stop-camera" class="btn-stop" disabled>カメラ停止</button>
            <button id="btn-toggle-recording" class="btn-record" disabled>録画開始</button>
            <button id="btn-capture-photo" class="btn-photo" disabled>写真撮影</button>
            <button id="btn-toggle-mode" class="btn-mode" disabled>表示モード: 全天球展開</button>
        </div>
        
        <div class="status-box">
            <h3>ステータス:</h3>
            <p>- このウェブアプリからデュアルフィッシュアイカメラを制御できます</p>
            <p>- 全天球展開モードでは、デュアルフィッシュアイ画像がリアルタイムに展開されます</p>
            <p>- 録画したビデオは自動的にMP4に変換されます</p>
            <p>- '表示モード'ボタンで表示形式を切り替えられます</p>
        </div>
    </div>
    
    <div class="notification" id="notification"></div>
    
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Elements
            const cameraStatus = document.getElementById('camera-status');
            const recordingStatus = document.getElementById('recording-status');
            const startButton = document.getElementById('btn-start-camera');
            const stopButton = document.getElementById('btn-stop-camera');
            const recordButton = document.getElementById('btn-toggle-recording');
            const photoButton = document.getElementById('btn-capture-photo');
            const modeButton = document.getElementById('btn-toggle-mode');
            const notification = document.getElementById('notification');
            
            // Display modes
            const displayModes = {
                'fisheye': 'デュアルフィッシュアイ',
                'equirectangular': '全天球展開'
            };
            
            // Update status
            function updateStatus() {
                fetch('/api/status')
                    .then(response => response.json())
                    .then(data => {
                        // Update camera status
                        if (data.camera === 'running') {
                            cameraStatus.textContent = 'カメラ: 動作中';
                            cameraStatus.style.color = 'green';
                            startButton.disabled = true;
                            stopButton.disabled = false;
                            recordButton.disabled = false;
                            photoButton.disabled = false;
                            modeButton.disabled = false;
                        } else {
                            cameraStatus.textContent = 'カメラ: 停止中';
                            cameraStatus.style.color = 'red';
                            startButton.disabled = false;
                            stopButton.disabled = true;
                            recordButton.disabled = true;
                            photoButton.disabled = true;
                            modeButton.disabled = true;
                        }
                        
                        // Update recording status
                        if (data.recording) {
                            recordingStatus.textContent = '録画: 録画中';
                            recordingStatus.style.color = 'red';
                            recordButton.textContent = '録画停止';
                            recordButton.style.backgroundColor = '#2196F3';
                        } else {
                            recordingStatus.textContent = '録画: 停止中';
                            recordingStatus.style.color = '';
                            recordButton.textContent = '録画開始';
                            recordButton.style.backgroundColor = '#f44336';
                        }
                        
                        // Update display mode button
                        const modeName = displayModes[data.display_mode] || data.display_mode;
                        modeButton.textContent = `表示モード: ${modeName}`;
                    })
                    .catch(error => console.error('Status error:', error));
            }
            
            // Show notification
            function showNotification(message, timeout = 3000) {
                notification.textContent = message;
                notification.style.display = 'block';
                
                setTimeout(() => {
                    notification.style.display = 'none';
                }, timeout);
            }
            
            // API request helper
            function apiRequest(endpoint, successCallback) {
                fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                })
                .then(response => response.json())
                .then(data => {
                    showNotification(data.message);
                    if (successCallback) successCallback(data);
                    updateStatus();
                })
                .catch(error => {
                    console.error('API error:', error);
                    showNotification('エラーが発生しました', 5000);
                });
            }
            
            // Event listeners
            startButton.addEventListener('click', function() {
                apiRequest('/api/start_camera');
            });
            
            stopButton.addEventListener('click', function() {
                apiRequest('/api/stop_camera');
            });
            
            recordButton.addEventListener('click', function() {
                apiRequest('/api/toggle_recording');
            });
            
            photoButton.addEventListener('click', function() {
                apiRequest('/api/capture_photo');
            });
            
            modeButton.addEventListener('click', function() {
                apiRequest('/api/toggle_display_mode', function(data) {
                    const modeName = displayModes[data.mode] || data.mode;
                    modeButton.textContent = `表示モード: ${modeName}`;
                });
            });
            
            // Initial status update
            updateStatus();
            
            // Periodic status updates
            setInterval(updateStatus, 5000);
        });
    </script>
</body>
</html>
"""

# Write template file
with open('templates/dual_fisheye_index.html', 'w') as f:
    f.write(html_template)

# Main function
def main():
    app.run(host='0.0.0.0', port=8081, debug=True)

if __name__ == '__main__':
    main()
