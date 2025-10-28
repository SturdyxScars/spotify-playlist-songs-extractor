from flask import Flask, render_template, request, send_file, flash, redirect, send_from_directory
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
import os
import logging
import tempfile
import threading

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

temp_files = {}
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
print(DOWNLOAD_FOLDER)



def extract_spotify_songs(playlist_url):
    """Extract songs from Spotify playlist using Selenium"""
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    try:
        # Set up driver with webdriver-manager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.get(playlist_url)
        wait = WebDriverWait(driver, 10)

        # Wait for playlist to load
        scrollable_div = wait.until(
            EC.presence_of_element_located((By.XPATH, '//div[@data-testid="playlist-tracklist"]'))
        )

        scroll_pause = 2
        all_songs = set()
        stable_rounds = 0
        max_scrolls = 20  # Safety limit

        scroll_count = 0
        while stable_rounds < 3 and scroll_count < max_scrolls:
            driver.execute_script("arguments[0].scrollBy(0, arguments[0].offsetHeight);", scrollable_div)
            time.sleep(scroll_pause)

            # Get currently visible songs
            songs = driver.find_elements(By.XPATH,
                                         '//div[@role="row"]//a[@data-testid="internal-track-link"]//div[@data-encore-id="text"]')
            current_titles = {song.text.strip() for song in songs if song.text.strip()}

            old_len = len(all_songs)
            all_songs.update(current_titles)

            if len(all_songs) == old_len:
                stable_rounds += 2
            else:
                stable_rounds = 0  # reset if we found new ones

            scroll_count += 1

        driver.quit()

        # Convert set to sorted list
        sorted_songs = sorted(all_songs)
        return sorted_songs, None

    except Exception as e:
        if 'driver' in locals():
            driver.quit()
        return None, str(e)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        playlist_url = request.form.get('playlist_url', '').strip()

        if not playlist_url:
            flash('Please enter a Spotify playlist URL', 'error')
            return render_template('index.html')

        # Validate Spotify URL
        if not playlist_url.startswith('https://open.spotify.com/playlist/'):
            flash('Please enter a valid Spotify playlist URL', 'error')
            return render_template('index.html')

        # Extract songs
        songs, error = extract_spotify_songs(playlist_url)

        if error:
            flash(f'Error extracting songs: {error}', 'error')
            return render_template('index.html')

        if not songs:
            flash('No songs found in this playlist', 'warning')
            return render_template('index.html')

        # Create temporary file

        file_temp = "songs.txt"
        download_path = os.path.join(DOWNLOAD_FOLDER, file_temp)
        with open(download_path, 'w', encoding='utf-8') as f:
            for i, song in enumerate(songs, start=1):
                f.write(f"{song}\n")
            f.close()

        return render_template('result.html',
                               songs=songs,
                               total_songs=len(songs),
                               file_temp=file_temp)

    return render_template('index.html')


@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    """Download the generated text file"""
    try:
        # Check if file exists in our storage
        download_flag = False
        logging.info('Downloading file= [%s]', filename)
        logging.info(app.root_path)
        full_path = os.path.join(app.root_path,DOWNLOAD_FOLDER)
        logging.info(full_path)
        return send_from_directory(full_path, filename, as_attachment=True)


    except Exception as e:
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect('/')


if __name__ == '__main__':
    app.run("localhost",debug=True)