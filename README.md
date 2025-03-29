# 360cam_gnss

## 概要
Raspberry Pi用のステレオスコピック360度カメラシステムとGNSS（全地球航法衛星システム）統合

## 機能
- ステレオスコピックカメラ撮影（左右2台のカメラ）
- 複数の表示モード（左右並列、左のみ、右のみ、アナグリフ3D）
- 動画録画と静止画撮影
- ウェブインターフェース（Flaskベース）でのカメラ制御

## インストール方法

### 依存パッケージ
```bash
sudo apt-get update
sudo apt-get install -y python3-picamera python3-opencv gpsd gpsd-clients python3-pip mp4box
```

### Python依存関係（Python 3.7用）
```bash
pip3 install -r py37_requirements.txt
```

## 使用方法

### コマンドラインでの使用
```bash
# カメラのみを起動して録画する
python3 start_camera.py

# 使用可能なコマンド:
# r - 録画開始/停止
# q - 終了
```

### ウェブアプリの使用
```bash
# Flaskベースのウェブインターフェースを起動
python3 web_camera_app.py
```

ブラウザで以下のURLにアクセスしてください：
```
http://ラズパイのIPアドレス:8080
```

ウェブアプリの機能:
- カメラ起動/停止
- 録画開始/停止
- 写真撮影
- 表示モード切替（左右並列、左のみ、右のみ、アナグリフ3D）
- リアルタイムカメラプレビュー

## ファイル構成
- `camera.py` - カメラクラスの実装
- `config.py` - 設定ファイル
- `start_camera.py` - シンプルなコマンドラインインターフェース
- `web_camera_app.py` - Flaskベースのウェブインターフェース
- `camera_app.py` - Fletベースのグラフィカルインターフェース（Python 3.9以上が必要）

## Python 3.7での実行について
Python 3.7で実行する場合は、以下の点に注意してください：
- `web_camera_app.py` はPython 3.7と互換性があります
- 依存パッケージをインストールする際には `py37_requirements.txt` を使用してください
- `camera_app.py`（Fletバージョン）はPython 3.9以上が必要です

## ライセンス
このプロジェクトはGNU General Public License v3.0の下でライセンスされています。
