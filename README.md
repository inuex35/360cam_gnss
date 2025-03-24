# 360Cam GNSS

Raspberry Pi CM4用の360度カメラとGNSSデータ収集システム。PPSを使用して時間同期を行います。

## 機能

- 360度カメラからの映像キャプチャと保存
- GNSS/GPSからのNMEAデータの取得とGPXファイルへの保存
- PPS（Pulse Per Second）信号を利用した時間同期
- 映像とGNSSデータの同期記録

## ハードウェア要件

- Raspberry Pi Compute Module 4
- 360度カメラ（OpenCVと互換性のあるUSBカメラ）
- GNSS/GPSモジュール（シリアル通信対応、PPSピン付き）
- microSDカード（高速・大容量推奨）

## ソフトウェア要件

- Raspberry Pi OS (32-bit/64-bit)
- Python 3.6以上
- OpenCV 4.x
- GPSライブラリ (pynmea2, gpxpy)
- RPi.GPIO

## インストール方法

```bash
# 必要なパッケージのインストール
sudo apt-get update
sudo apt-get install -y python3-opencv python3-pip python3-rpi.gpio gpsd gpsd-clients

# Pythonライブラリのインストール
pip3 install pynmea2 gpxpy

# リポジトリのクローン
git clone https://github.com/inuex35/360cam_gnss.git
cd 360cam_gnss
```

## 使用方法

1. ハードウェアの接続
   - 360度カメラをUSBポートに接続
   - GPSモジュールをシリアルポート(UART)に接続
   - GPSモジュールのPPSピンをRaspberry PiのGPIOピンに接続（デフォルト: GPIO18）
   
2. 設定ファイルの編集
   ```bash
   nano config.py
   ```
   
3. プログラム実行
   ```bash
   python3 main.py
   ```

## ファイル構成

- `main.py`: メインプログラム
- `config.py`: 設定ファイル
- `camera.py`: 360度カメラモジュール
- `gnss.py`: GNSSデータ処理モジュール
- `sync.py`: PPS同期モジュール
- `utils.py`: ユーティリティ関数
- `data/`: 保存されたデータディレクトリ

## ライセンス

GPLv3
