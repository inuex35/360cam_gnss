#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Simple script to just start the camera without other functionality

import time
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
        
        try:
            # Keep the script running
            print("カメラが起動中です。終了するには Ctrl+C を押してください...")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nプログラムを終了します...")
        finally:
            # Cleanup
            camera.stop()
            print("カメラを停止しました")
    else:
        print("カメラの初期化に失敗しました")

if __name__ == "__main__":
    main()
