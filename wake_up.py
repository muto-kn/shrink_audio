from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

# あなたのStreamlitアプリのURLに書き換えてください
APP_URL = "https://shrink-audio-gr23lddtaowhgk6jeqystb.streamlit.app/"


def run_waker():
    print("⏰ 起床プロセスを開始します...")

    # Chromeの設定（ヘッドレスモード＝画面なしで動くモード）
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # ドライバーのセットアップ
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # アプリにアクセス
        driver.get(APP_URL)
        print(f"🚀 アクセスしました: {APP_URL}")

        # 読み込み待ち（60秒待機して、しっかり起こす）
        time.sleep(60)

        # タイトルを取得して確認
        print(f"📄 ページタイトル: {driver.title}")
        print("✅ 完了しました。")

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")

    finally:
        driver.quit()


if __name__ == "__main__":
    run_waker()
