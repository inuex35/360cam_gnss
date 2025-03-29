# 360cam_gnss

## 概要
Raspberry Pi用のステレオスコピック360度カメラシステムとGNSS（全地球航法衛星システム）統合

## 機能
- ステレオスコピックカメラ撮影（左右2台のカメラ）
- 複数の表示モード（左右並列、左のみ、右のみ、アナグリフ3D）
- 動画録画と静止画撮影
- Fletを使用したグラフィカルユーザーインターフェース

## インストール方法

### 依存パッケージ
```bash
sudo apt-get update
sudo apt-get install -y python3-picamera python3-opencv gpsd gpsd-clients python3-pip mp4box
```

### Python依存関係
```bash
pip install -r requirements.txt
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

### GUIアプリの使用
```bash
# Fletベースのグラフィカルインターフェースを起動
python3 camera_app.py
```

GUI機能:
- カメラ起動/停止
- 録画開始/停止
- 写真撮影
- 表示モード切替（左右並列、左のみ、右のみ、アナグリフ3D）

## ファイル構成
- `camera.py` - カメラクラスの実装
- `config.py` - 設定ファイル
- `start_camera.py` - シンプルなコマンドラインインターフェース
- `camera_app.py` - Fletベースのグラフィカルインターフェース

## リモート操作
Fletアプリはネットワーク経由でリモート操作が可能です。
```bash
# Raspberry Piで以下を実行してリモートアクセスを有効にする
python3 -m flet.web camera_app.py
```

その後、Raspberry PiのIPアドレスとポート8550にブラウザからアクセスできます：
```
http://raspi-ip:8550
```

## ライセンス
このプロジェクトはGNU General Public License v3.0の下でライセンスされています。
