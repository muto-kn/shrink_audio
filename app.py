import streamlit as st
import os
import subprocess
import shutil
import re
import time
import uuid
import json  # 情報解析用にjsonモジュールを追加

# --- 設定 ---
TARGET_SIZE_MB = 80
TEMP_DIR = "temp"

# --- パス設定 ---
if shutil.which("ffmpeg"):
    FFMPEG_PATH = "ffmpeg"
    FFPROBE_PATH = "ffprobe"
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FFMPEG_PATH = os.path.join(BASE_DIR, "bin", "ffmpeg.exe")
    FFPROBE_PATH = os.path.join(BASE_DIR, "bin", "ffprobe.exe")

# --- 初期化＆お掃除 ---
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)
else:
    current_time = time.time()
    for f in os.listdir(TEMP_DIR):
        f_path = os.path.join(TEMP_DIR, f)
        try:
            if (
                os.path.isfile(f_path)
                and current_time - os.path.getctime(f_path) > 3600
            ):
                os.remove(f_path)
        except Exception:
            pass

st.set_page_config(page_title="Gemini音声縮小ツール Pro", page_icon="🎛️")

# --- 関数群 ---


def get_audio_info(file_path):
    """ffprobeを使って詳細なメディア情報を取得する"""
    cmd = [
        FFPROBE_PATH,
        "-v",
        "error",
        "-show_entries",
        "format=duration,bit_rate,format_name:stream=codec_name,channels,sample_rate",
        "-of",
        "json",
        file_path,
    ]
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        info = json.loads(result.stdout)

        # 必要な情報を辞書にまとめる
        format_info = info.get("format", {})
        # ストリーム情報（音声ストリームを探す）
        streams = info.get("streams", [])
        audio_stream = next(
            (s for s in streams if s.get("codec_type") == "audio"),
            streams[0] if streams else {},
        )

        return {
            "duration": float(format_info.get("duration", 0)),
            "bit_rate": int(format_info.get("bit_rate", 0)),  # 全体のビットレート
            "format_name": format_info.get("format_name", "unknown"),
            "codec_name": audio_stream.get("codec_name", "unknown"),
            "channels": int(audio_stream.get("channels", 0)),
            "sample_rate": int(audio_stream.get("sample_rate", 0)),
        }
    except Exception as e:
        return None


def format_time_jp(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}時間{m}分{s}秒"
    return f"{m}分{s}秒"


def convert_time_str_to_seconds(time_str):
    try:
        h, m, s = time_str.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except:
        return 0.0


def compress_audio_with_progress(input_file, output_file, duration_sec, target_kbps):
    """指定されたビットレートで圧縮を実行"""

    # コマンド構築
    cmd = [
        FFMPEG_PATH,
        "-i",
        input_file,
        "-vn",  # 映像削除
        "-c:a",
        "aac",  # コーデック
        "-ac",
        "1",  # モノラル固定
        "-ar",
        "16000",  # 16kHz固定
        "-b:a",
        f"{target_kbps}k",  # ユーザー指定のビットレート
        "-y",
        output_file,
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
    )

    progress_bar = st.progress(0)
    status_text = st.empty()
    start_time = time.time()
    time_pattern = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d+)")

    while True:
        line = process.stderr.readline()
        if not line and process.poll() is not None:
            break
        if line:
            match = time_pattern.search(line)
            if match:
                current_sec = convert_time_str_to_seconds(match.group(1))
                progress = min(current_sec / duration_sec, 1.0)
                elapsed_time = time.time() - start_time
                progress_bar.progress(progress)
                status_text.write(
                    f"🔄 変換中... {int(progress*100)}% (経過: {elapsed_time:.1f}秒)"
                )

    if process.returncode == 0:
        progress_bar.progress(100)
        status_text.empty()
        return True, time.time() - start_time
    else:
        return False, 0


# --- メイン画面 ---
st.title("🎛️ Gemini用 音声縮小ツール Pro")
st.write("ファイル情報を確認し、音質と容量をコントロールできます。")

uploaded_file = st.file_uploader("ファイルをアップロード", type=None)

if uploaded_file:
    # --- 1. ファイル保存と解析 ---
    unique_id = str(uuid.uuid4())
    original_name = uploaded_file.name
    safe_name = f"{unique_id}_{original_name}"
    input_path = os.path.join(TEMP_DIR, safe_name)

    # Streamlitは再実行されるたびにここを通るので、
    # 既にファイルがある場合は保存をスキップしないと無駄なIOが発生するが、
    # シンプルにするため毎回上書き保存する（小規模なら問題なし）
    with open(input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # 解析実行
    info = get_audio_info(input_path)

    if info:
        # --- 2. 現在の情報を表示 ---
        st.subheader("📊 現在のファイル情報")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("ファイル形式", info["format_name"].split(",")[0])
        with col2:
            st.metric("再生時間", format_time_jp(info["duration"]))
        with col3:
            # チャンネル判定
            ch_str = (
                "ステレオ (2ch)"
                if info["channels"] == 2
                else f"モノラル ({info['channels']}ch)"
            )
            st.metric("チャンネル", ch_str)
        with col4:
            # 元のビットレート (kbps)
            orig_kbps = int(info["bit_rate"] / 1000) if info["bit_rate"] > 0 else "不明"
            st.metric("ビットレート", f"{orig_kbps} kbps")

        st.divider()  # 区切り線

        # --- 3. 音質設定と容量予測 ---
        st.subheader("🛠️ 変換設定")

        # 自動計算 (80MBターゲット)
        # 目標ビットレート = (80MB * 8bit) / 秒数 * 0.9(マージン)
        target_bits_80mb = TARGET_SIZE_MB * 1024 * 1024 * 8
        auto_kbps_calc = (target_bits_80mb / info["duration"]) * 0.9 / 1000
        auto_kbps = int(max(12, min(auto_kbps_calc, 128)))  # 12k~128kの範囲

        # 選択肢の作成
        bitrate_options = [12, 16, 24, 32, 48, 64, 96, 128, 160, 192]

        # 自動計算値に一番近い選択肢をデフォルトにする
        default_index = min(
            range(len(bitrate_options)),
            key=lambda i: abs(bitrate_options[i] - auto_kbps),
        )

        # ドロップダウン
        selected_kbps = st.selectbox(
            "ビットレートを選択 (数値が大きいほど高音質・大容量)",
            options=bitrate_options,
            index=default_index,
            format_func=lambda x: f"{x} kbps {'(推奨)' if x == bitrate_options[default_index] else ''}",
        )

        # 容量予測計算 (音声のみの概算)
        # サイズ(MB) = kbps * 秒数 / 8 / 1024
        predicted_size_mb = (selected_kbps * info["duration"]) / 8 / 1024

        # 予測表示
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            st.info(f"💾 予想ファイルサイズ: **約 {predicted_size_mb:.2f} MB**")
        with p_col2:
            if predicted_size_mb > TARGET_SIZE_MB:
                st.warning(f"⚠️ {TARGET_SIZE_MB}MBを超える可能性があります")
            else:
                st.success(f"✅ {TARGET_SIZE_MB}MB以内に収まる予定です")

        # --- 4. 変換実行ボタン ---
        if st.button("変換スタート", type="primary"):
            output_name = os.path.splitext(original_name)[0] + "_gemini.m4a"
            output_path = os.path.join(TEMP_DIR, f"processed_{unique_id}_{output_name}")

            success, processing_time = compress_audio_with_progress(
                input_path, output_path, info["duration"], selected_kbps
            )

            if success:
                out_size = os.path.getsize(output_path) / (1024 * 1024)
                st.success("✅ 完了しました！")
                st.write(
                    f"結果: **{out_size:.2f} MB** (処理時間: {processing_time:.2f}秒)"
                )

                with open(output_path, "rb") as f:
                    st.download_button(
                        label="📥 ダウンロード",
                        data=f,
                        file_name=output_name,
                        mime="audio/mp4",
                    )

                # 元ファイル削除
                try:
                    os.remove(input_path)
                except:
                    pass

    else:
        st.error("ファイル情報の解析に失敗しました。")
        # 解析失敗時は入力ファイルを消しておく
        try:
            os.remove(input_path)
        except:
            pass
