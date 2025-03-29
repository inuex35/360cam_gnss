#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Script to start the camera and allow video recording

import time
import os
from camera import Camera

def main():
    # Initialize camera instance
    camera = Camera()
    
    # Open and start the camera
    if camera.open():
        print("カメラが正常に初期化されました")
        
        # Start camera capture
        camera.start()
        print("カメラのキャプチャを開始しました")
        
        recording = False
        
        try:
            print("コマンド:")
            print("  r - 録画開始/停止")
            print("  q - 終了")
            
            while True:
                user_input = input("コマンドを入力してください (r/q): ")
                
                if user_input.lower() == 'r':
                    if not recording:
                        # Start recording
                        camera.start_recording()
                        recording = True
                        print("録画を開始しました")
                    else:
                        # Stop recording
                        camera.stop_recording()
                        recording = False
                        print("録画を停止しました")
                        
                elif user_input.lower() == 'q':
                    # Exit program
                    print("終了します...")
                    break
                
                else:
                    print("無効なコマンドです。'r'で録画開始/停止、'q'で終了します")
                
        except KeyboardInterrupt:
            print("\nプログラムを終了します...")
        finally:
            # Stop recording if still recording
            if recording:
                camera.stop_recording()
                print("録画を停止しました")
            
            # Cleanup
            camera.stop()
            print("カメラを停止しました")
            
            # Show recording location
            base_path = os.path.join(os.getcwd(), 'data', 'videos')
            if os.path.exists(base_path):
                print(f"録画したビデオは {base_path} に保存されています")
    else:
        print("カメラの初期化に失敗しました")

if __name__ == "__main__":
    main()
