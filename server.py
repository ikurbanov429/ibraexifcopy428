import logging
import mimetypes
import os
import time
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template, request, send_from_directory, flash, redirect, url_for
from werkzeug.utils import secure_filename
from PIL import Image
import piexif
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__server__)
app.config['UPLOAD_FOLDER'] = 'uploads/'  # Переместите папку за пределы static
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Лимит 16 MB
app.secret_key = 'supersecretkey'

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type and mime_type.startswith('image/')

def copy_exif_and_quality(source_image_path, target_image_path):
    try:
        source_image = Image.open(source_image_path)
        exif_data = piexif.load(source_image.info.get("exif", b""))
        target_image = Image.open(target_image_path)
        target_image.save(target_image_path, exif=piexif.dump(exif_data), quality=100)
    except Exception as e:
        logger.error(f"Ошибка при копировании EXIF-данных: {str(e)}")
        raise

def cleanup_uploads():
    now = time.time()
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(file_path):
            file_age = now - os.path.getmtime(file_path)
            if file_age > 3600:  # Удаляем файлы старше 1 часа
                os.remove(file_path)
                logger.info(f"Удален старый файл: {filename}")

scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_uploads, 'interval', hours=1)
scheduler.start()

executor = ThreadPoolExecutor(2)

def async_copy_exif_and_quality(source_path, target_path):
    try:
        copy_exif_and_quality(source_path, target_path)
    except Exception as e:
        logger.error(f"Ошибка в асинхронной задаче: {str(e)}")

@app.errorhandler(413)
def request_entity_too_large(error):
    flash("Ошибка: файл слишком большой. Максимальный размер — 16 МБ.")
    return redirect(url_for('index'))

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'source_image' not in request.files or 'target_image' not in request.files:
            flash("Ошибка: файлы не загружены.")
            return redirect(request.url)

        source_image = request.files['source_image']
        target_image = request.files['target_image']

        if source_image.filename == '' or target_image.filename == '':
            flash("Ошибка: файлы не выбраны.")
            return redirect(request.url)

        if not allowed_file(source_image.filename) or not allowed_file(target_image.filename):
            flash("Ошибка: разрешены только файлы с расширениями .png, .jpg, .jpeg, .gif.")
            return redirect(request.url)

        source_filename = secure_filename(source_image.filename)
        target_filename = secure_filename(target_image.filename)

        source_path = os.path.join(app.config['UPLOAD_FOLDER'], source_filename)
        target_path = os.path.join(app.config['UPLOAD_FOLDER'], target_filename)

        try:
            source_image.save(source_path)
            target_image.save(target_path)
            executor.submit(async_copy_exif_and_quality, source_path, target_path)
            flash("Успешно! Обработка изображения начата.")
            download_link = target_filename
        except Exception as e:
            flash(f"Ошибка: {str(e)}")
            if os.path.exists(source_path):
                os.remove(source_path)
            if os.path.exists(target_path):
                os.remove(target_path)

    return render_template('index.html')

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    response = send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    response.call_on_close(lambda: os.remove(file_path))
    return response

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(host='0.0.0.0', port=5000)