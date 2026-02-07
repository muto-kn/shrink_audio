import streamlit as st
import os
import subprocess
import shutil
import re
import time  # 時間計測用に追加

# --- 設定 ---
TARGET_SIZE_MB = 75
TEMP_DIR = "temp"

# --- パス設定 (Web/Local両対応) ---
if shutil.which("ffmpeg"):
    FFMPEG_PATH = "ffmpeg"
    FFPROBE_PATH = "ffprobe"
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FFMPEG_PATH = os.path.join(BASE_DIR, "bin", "ffmpeg.exe")
    FFPROBE_PATH = os.path.join(BASE_DIR, "bin", "ffprobe.exe")

# --- 初期化 ---
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

st.set_page_config(page_title="Gemini音声縮小ツール", page_icon="🎙️")

# --- 関数群 ---


def get_duration(file_path):
    """動画・音声の総再生時間（秒）を取得"""
    cmd = [
        FFPROBE_PATH,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return float(result.stdout.strip())
    except:
        return None


def format_time_jp(seconds):
    """秒数を「●分●秒」形式に"""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}時間{m}分{s}秒"
    return f"{m}分{s}秒"


def convert_time_str_to_seconds(time_str):
    """FFmpegの出力(HH:MM:SS.ms)を秒数(float)に変換"""
    try:
        h, m, s = time_str.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except:
        return 0.0


def compress_audio_with_progress(input_file, output_file, duration_sec):
    """進捗バー＆経過時間付きで圧縮処理を実行"""

    # 1. ビットレート計算
    target_bits = TARGET_SIZE_MB * 1024 * 1024 * 8
    calculated_bitrate = (target_bits / duration_sec) * 0.9
    bitrate_kbps = int(calculated_bitrate / 1000)

    # Gemini最適化 (12kbps ~ 64kbps)
    final_bitrate = max(12, min(bitrate_kbps, 64))

    st.info(f"🎯 設定: モノラル / 16kHz / {final_bitrate} kbps")

    # 2. FFmpegコマンド
    cmd = [
        FFMPEG_PATH,
        "-i",
        input_file,
        "-vn",
        "-c:a",
        "aac",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        f"{final_bitrate}k",
        "-y",
        output_file,
    ]

    # 3. プロセス実行
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
    )

    # UI要素
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 時間計測開始
    start_time = time.time()

    time_pattern = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d+)")

    while True:
        line = process.stderr.readline()
        if not line and process.poll() is not None:
            break

        if line:
            match = time_pattern.search(line)
            if match:
                current_time_str = match.group(1)
                current_sec = convert_time_str_to_seconds(current_time_str)

                # 進捗率
                progress = min(current_sec / duration_sec, 1.0)

                # 経過時間
                elapsed_time = time.time() - start_time

                # UI更新
                progress_bar.progress(progress)
                status_text.write(
                    f"🔄 変換中... {int(progress*100)}% (経過: {elapsed_time:.1f}秒)"
                )

    # 終了処理
    end_time = time.time()
    total_processing_time = end_time - start_time

    if process.returncode == 0:
        progress_bar.progress(100)
        status_text.empty()  # 途中経過を消す
        return True, total_processing_time
    else:
        return False, 0


# --- メイン画面 ---
st.title("🎙️ Gemini用 音声縮小ツール")

uploaded_file = st.file_uploader("ファイルをアップロード (mp4, mov, mp3...)", type=None)

if uploaded_file:
    size_mb = uploaded_file.size / (1024 * 1024)
    st.write(f"📁 入力サイズ: {size_mb:.2f} MB")

    if st.button("変換スタート", type="primary"):
        input_path = os.path.join(TEMP_DIR, uploaded_file.name)
        output_name = os.path.splitext(uploaded_file.name)[0] + "_gemini.m4a"
        output_path = os.path.join(TEMP_DIR, output_name)

        with open(input_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        total_duration = get_duration(input_path)

        if total_duration:
            st.write(f"⏱️ 動画の長さ: {format_time_jp(total_duration)}")

            # 処理実行
            success, processing_time = compress_audio_with_progress(
                input_path, output_path, total_duration
            )

            if success:
                out_size = os.path.getsize(output_path) / (1024 * 1024)

                # 完了メッセージと処理時間
                st.success(f"✅ 完了しました！")
                st.info(
                    f"⚡ 処理時間: {processing_time:.2f}秒 (サイズ: {out_size:.2f} MB)"
                )

                with open(output_path, "rb") as f:
                    st.download_button(
                        label="📥 ダウンロード",
                        data=f,
                        file_name=output_name,
                        mime="audio/mp4",
                    )
        else:
            st.error("時間の取得に失敗しました")
