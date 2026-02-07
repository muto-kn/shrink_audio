import streamlit as st
import os
import subprocess
import re
import time
import shutil

# --- 設定 ---
TARGET_SIZE_MB = 80
TEMP_DIR = "temp"


# --- パス設定 (Webとローカルの両対応) ---
# サーバー上に ffmpeg があるか確認
if shutil.which("ffmpeg"):
    # Webサーバー(Streamlit Cloud)用
    FFMPEG_PATH = "ffmpeg"
    FFPROBE_PATH = "ffprobe"
else:
    # ローカル(Windows)用
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
    """進捗バー付きで圧縮処理を実行"""

    # 1. ビットレート計算 (Gemini最適化)
    target_bits = TARGET_SIZE_MB * 1024 * 1024 * 8
    calculated_bitrate = (target_bits / duration_sec) * 0.9
    bitrate_kbps = int(calculated_bitrate / 1000)

    # Gemini向け調整 (モノラル・低ビットレート)
    final_bitrate = bitrate_kbps
    if final_bitrate < 12:
        final_bitrate = 12
    elif final_bitrate > 64:
        final_bitrate = 64

    st.info(f"🎯 設定: モノラル / 16kHz / {final_bitrate} kbps")

    # 2. FFmpegコマンド
    cmd = [
        FFMPEG_PATH,
        "-i",
        input_file,
        "-vn",  # 映像削除
        "-c:a",
        "aac",  # AAC
        "-ac",
        "1",  # モノラル
        "-ar",
        "16000",  # 16kHz
        "-b:a",
        f"{final_bitrate}k",
        "-y",  # 上書き
        output_file,
    ]

    # 3. プロセス実行と進捗監視
    # stderr=subprocess.PIPE でFFmpegのログを受け取る
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,  # テキストとして扱う
        encoding="utf-8",  # Windowsでの文字化け防止
    )

    # StreamlitのUI要素を用意
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 正規表現: "time=00:01:23.45" を探すパターン
    time_pattern = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d+)")

    while True:
        # 1行ずつ読み込む
        line = process.stderr.readline()
        if not line and process.poll() is not None:
            break  # 処理終了

        if line:
            # ログから時間を探す
            match = time_pattern.search(line)
            if match:
                current_time_str = match.group(1)
                current_sec = convert_time_str_to_seconds(current_time_str)

                # 進捗率計算 (0.0 ~ 1.0)
                progress = current_sec / duration_sec
                progress = min(progress, 1.0)  # 100%を超えないように

                # UI更新
                progress_bar.progress(progress)
                status_text.text(f"変換中... {int(progress*100)}% ({current_time_str})")

    # 終了コード確認
    if process.returncode == 0:
        progress_bar.progress(100)  # 念のため100%にする
        status_text.text("完了！")
        return True
    else:
        st.error("エラーが発生しました。")
        return False


# --- メイン画面 ---
st.title("🎙️ Gemini用 音声縮小ツール")

uploaded_file = st.file_uploader(
    "ファイルをアップロード (mp4, mov, mp3, wav...)", type=None
)

if uploaded_file:
    # ファイルサイズ表示
    size_mb = uploaded_file.size / (1024 * 1024)
    st.write(f"📁 入力サイズ: {size_mb:.2f} MB")

    if st.button("変換スタート", type="primary"):
        input_path = os.path.join(TEMP_DIR, uploaded_file.name)
        output_name = os.path.splitext(uploaded_file.name)[0] + "_gemini.m4a"
        output_path = os.path.join(TEMP_DIR, output_name)

        # 保存
        with open(input_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # 総時間を先に取得
        total_duration = get_duration(input_path)

        if total_duration:
            st.write(f"⏱️ 総再生時間: {format_time_jp(total_duration)}")

            # 進捗バー付きで実行
            success = compress_audio_with_progress(
                input_path, output_path, total_duration
            )

            if success:
                out_size = os.path.getsize(output_path) / (1024 * 1024)
                st.success(f"✅ 完了しました！ ({out_size:.2f} MB)")

                with open(output_path, "rb") as f:
                    st.download_button(
                        label="📥 ダウンロード",
                        data=f,
                        file_name=output_name,
                        mime="audio/mp4",
                    )
        else:
            st.error("ファイルの時間を取得できませんでした。")
