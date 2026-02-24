import streamlit as st
import os
import subprocess
import shutil
import re
import time
import uuid
import json

# --- 設定 ---
TARGET_SIZE_MB = 70
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

st.set_page_config(page_title="AIアシスタント用 音声縮小ツール", page_icon="🎛️")

# --- CSSで見栄えを調整 ---
st.markdown(
    """
<style>
    .info-box {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .info-label {
        font-size: 12px;
        color: #555;
    }
    .info-value {
        font-size: 14px;
        font-weight: bold;
        color: #000;
        word-wrap: break-word; /* 長い文字を折り返す */
    }
</style>
""",
    unsafe_allow_html=True,
)

# --- 関数群 ---


def get_audio_info(file_path):
    """詳細なメディア情報を取得"""
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

        format_info = info.get("format", {})
        streams = info.get("streams", [])
        audio_stream = next(
            (s for s in streams if s.get("codec_type") == "audio"),
            streams[0] if streams else {},
        )

        return {
            "duration": float(format_info.get("duration", 0)),
            "bit_rate": int(format_info.get("bit_rate", 0)),
            "format_name": format_info.get("format_name", "unknown"),
            "codec_name": audio_stream.get("codec_name", "unknown"),
            "channels": int(audio_stream.get("channels", 0)),
            "sample_rate": int(audio_stream.get("sample_rate", 0)),
        }
    except Exception:
        return None


def format_time_jp(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    parts = []
    if h > 0:
        parts.append(f"{h}時間")
    if m > 0:
        parts.append(f"{m}分")
    parts.append(f"{s}秒")
    return "".join(parts)


def convert_time_str_to_seconds(time_str):
    try:
        h, m, s = time_str.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except:
        return 0.0


def compress_audio_custom(input_file, output_file, duration_sec, settings):
    """ユーザー設定に基づいて変換を実行"""

    # settings = {'kbps': 64, 'channels': 1, 'format': 'm4a'}

    # フォーマットごとのコーデック指定
    if settings["format"] == "m4a":
        audio_codec = "aac"
    else:  # mp3
        audio_codec = "libmp3lame"

    cmd = [
        FFMPEG_PATH,
        "-i",
        input_file,
        "-vn",  # 映像削除
        "-c:a",
        audio_codec,  # コーデック (aac or libmp3lame)
        "-ac",
        str(settings["channels"]),  # チャンネル数 (1 or 2)
        "-ar",
        "16000",  # サンプリングレート(16kHz固定)
        "-b:a",
        f"{settings['kbps']}k",  # ビットレート
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
st.title("🎛️ AIアシスタント用 音声縮小ツール")
st.write("ファイル情報を確認し、形式・チャンネル・音質を細かく設定できます。")

uploaded_file = st.file_uploader("ファイルをアップロード", type=None)

if uploaded_file:
    # --- 1. 保存と解析 ---
    unique_id = str(uuid.uuid4())
    original_name = uploaded_file.name
    safe_name = f"{unique_id}_{original_name}"
    input_path = os.path.join(TEMP_DIR, safe_name)

    with open(input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    info = get_audio_info(input_path)

    if info:
        # --- 2. 情報をコンパクトに表示 (HTMLを使用) ---
        st.markdown("### 📊 ファイル情報")

        # 4つの情報を並べる
        cols = st.columns(4)

        # 情報をリスト化してループ処理
        info_items = [
            ("形式", info["format_name"].split(",")[0]),
            ("時間", format_time_jp(info["duration"])),
            (
                "Ch",
                f"{'ステレオ' if info['channels'] == 2 else 'モノラル'} ({info['channels']}ch)",
            ),
            (
                "Bitrate",
                f"{int(info['bit_rate']/1000) if info['bit_rate'] else '?'} kbps",
            ),
        ]

        for col, (label, value) in zip(cols, info_items):
            with col:
                # metricを使わず、HTMLで小さく表示
                st.markdown(
                    f"""
                <div class="info-box">
                    <div class="info-label">{label}</div>
                    <div class="info-value">{value}</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

        st.divider()

        # --- 3. 詳細設定 (ユーザーが選べる) ---
        st.subheader("🛠️ 変換設定")

        # 設定エリアを3列に分ける
        set_col1, set_col2, set_col3 = st.columns(3)

        with set_col1:
            # 形式選択 (m4a or mp3)
            out_format = st.selectbox(
                "出力形式",
                ["m4a (推奨)", "mp3"],
                index=0,  # m4aをデフォルト
                help="m4a(AAC)の方が高音質・低容量です。",
            )
            # 文字列処理："m4a (推奨)" -> "m4a"
            selected_format = "m4a" if "m4a" in out_format else "mp3"

        with set_col2:
            # チャンネル選択 (モノラル or ステレオ)
            out_channel = st.selectbox(
                "チャンネル",
                ["モノラル (推奨)", "ステレオ"],
                index=0,  # モノラルをデフォルト
                help="音声認識用ならモノラルで十分です。",
            )
            selected_channel_num = 1 if "モノラル" in out_channel else 2

        with set_col3:
            # ビットレート選択
            # 自動計算 (80MBターゲット)
            target_bits_80mb = TARGET_SIZE_MB * 1024 * 1024 * 8
            auto_kbps_calc = (target_bits_80mb / info["duration"]) * 0.9 / 1000

            # ステレオの場合はビットレートを少し多めに見積もる補正を入れてもいいが
            # 今回はあくまで「80MBに収める」計算を優先
            auto_kbps = int(max(12, min(auto_kbps_calc, 192)))

            bitrate_options = [12, 16, 24, 32, 48, 64, 96, 128, 160, 192, 256, 320]
            default_index = min(
                range(len(bitrate_options)),
                key=lambda i: abs(bitrate_options[i] - auto_kbps),
            )

            selected_kbps = st.selectbox(
                "ビットレート (kbps)",
                options=bitrate_options,
                index=default_index,
                format_func=lambda x: f"{x}k {'(推奨)' if x == bitrate_options[default_index] else ''}",
            )

        # --- 4. 容量予測 ---
        # 予測サイズ(MB) = kbps * 秒数 / 8 / 1024
        predicted_size_mb = (selected_kbps * info["duration"]) / 8 / 1024

        # 警告ロジック
        msg_func = st.success
        msg_icon = "✅"
        if predicted_size_mb > TARGET_SIZE_MB:
            msg_func = st.warning
            msg_icon = "⚠️"

        st.markdown(
            f"""
        <div style="background-color:#e8f0fe; padding:15px; border-radius:10px; margin-top:10px;">
            <b>{msg_icon} 予想ファイルサイズ: 約 {predicted_size_mb:.2f} MB</b><br>
            <small style="color:#666;">目標: {TARGET_SIZE_MB}MB以内</small>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # --- 5. 実行 ---
        if st.button("変換スタート", type="primary"):
            # 出力ファイル名を作成 (拡張子を動的に変える)
            output_name = (
                os.path.splitext(original_name)[0] + f"_downsized.{selected_format}"
            )
            output_path = os.path.join(TEMP_DIR, f"processed_{unique_id}_{output_name}")

            # 設定をまとめる
            settings = {
                "format": selected_format,
                "channels": selected_channel_num,
                "kbps": selected_kbps,
            }

            success, processing_time = compress_audio_custom(
                input_path, output_path, info["duration"], settings
            )

            if success:
                out_size = os.path.getsize(output_path) / (1024 * 1024)
                st.balloons()  # 完了時に風船を飛ばす演出
                st.success("✅ 完了しました！")
                st.info(f"結果: {out_size:.2f} MB (処理時間: {processing_time:.2f}秒)")

                # MIMEタイプの設定
                mime_type = "audio/mp4" if selected_format == "m4a" else "audio/mpeg"

                with open(output_path, "rb") as f:
                    st.download_button(
                        label=f"📥 {output_name} をダウンロード",
                        data=f,
                        file_name=output_name,
                        mime=mime_type,
                    )

                try:
                    os.remove(input_path)
                except:
                    pass

    else:
        st.error("ファイル情報の解析に失敗しました。")
        try:
            os.remove(input_path)
        except:
            pass
