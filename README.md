# 360cam_gnss

## 概要
Raspberry Pi用のステレオスコピック360度カメラシステムとGNSS（全地球航法衛星システム）統合

## 機能
- ステレオスコピックカメラ撮影（左右2台のカメラ）
- デュアルフィッシュアイカメラサポート（全天球変換）
- 複数の表示モード
  - ステレオカメラ: 左右並列、左のみ、右のみ、アナグリフ3D
  - デュアルフィッシュアイ: フィッシュアイ、全天球展開（equirectangular）
- 動画録画と静止画撮影
- ウェブインターフェース（Flaskベース）でのカメラ制御

## インストール方法

### 依存パッケージ
```bash
sudo apt-get update
sudo apt-get install -y python3-picamera python3-opencv gpsd gpsd-clients python3-pip mp4box
```

### PiCamera2のインストール（デュアルフィッシュアイカメラ用）
```bash
pip3 install picamera2
```

### Python依存関係（Python 3.7用）
```bash
pip3 install -r py37_requirements.txt
```

## 使用方法

### コマンドラインでの使用
```bash
# ステレオカメラを起動して録画する
python3 start_camera.py

# デュアルフィッシュアイカメラを起動する
python3 start_dual_fisheye.py

# 使用可能なコマンド:
# r - 録画開始/停止
# d - 表示モード切替
# p - 写真撮影（デュアルフィッシュアイの場合）
# q - 終了
```

### ウェブアプリの使用
```bash
# ステレオカメラ用のウェブインターフェースを起動
python3 web_camera_app.py

# デュアルフィッシュアイカメラ用のウェブインターフェースを起動
python3 web_dual_fisheye_app.py
```

ブラウザで以下のURLにアクセスしてください：
```
# ステレオカメラ用ウェブインターフェース
http://ラズパイのIPアドレス:8080

# デュアルフィッシュアイカメラ用ウェブインターフェース
http://ラズパイのIPアドレス:8081
```

ウェブアプリの機能:
- カメラ起動/停止
- 録画開始/停止
- 写真撮影
- 表示モード切替
- リアルタイムカメラプレビュー

## デュアルフィッシュアイカメラの全天球変換について
デュアルフィッシュアイカメラのサポートにより、2つのフィッシュアイレンズ画像をリアルタイムで全天球（equirectangular）形式に変換して表示・録画できます。この変換処理はOpenCVのremap関数を使用して実装されています。設定パラメータは`config.py`の`DUAL_FISHEYE_CONFIG`セクションで調整可能です。

## ファイル構成
- `camera.py` - ステレオカメラクラスの実装
- `dual_fisheye_camera.py` - デュアルフィッシュアイカメラクラスの実装
- `config.py` - 設定ファイル
- `start_camera.py` - ステレオカメラ用のシンプルなコマンドラインインターフェース
- `start_dual_fisheye.py` - デュアルフィッシュアイカメラ用のコマンドラインインターフェース
- `web_camera_app.py` - ステレオカメラ用のFlaskベースのウェブインターフェース
- `web_dual_fisheye_app.py` - デュアルフィッシュアイカメラ用のFlaskベースのウェブインターフェース
- `camera_app.py` - Fletベースのグラフィカルインターフェース（Python 3.9以上が必要）

## Python 3.7での実行について
Python 3.7で実行する場合は、以下の点に注意してください：
- `web_camera_app.py`と`web_dual_fisheye_app.py`はPython 3.7と互換性があります
- 依存パッケージをインストールする際には `py37_requirements.txt` を使用してください
- `camera_app.py`（Fletバージョン）はPython 3.9以上が必要です

## ライセンス
このプロジェクトはGNU General Public License v3.0の下でライセンスされています。
