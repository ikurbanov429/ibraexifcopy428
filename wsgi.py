import sys
import os

# Добавляем путь к вашему проекту в sys.path
path = '/home/ikurbanov429/ibraexifcopy428'
if path not in sys.path:
    sys.path.append(path)

# Включение поддержки потоков для uWSGI
os.environ['UWSGI_ENABLE_THREADS'] = '1'

# Импортируем ваше Flask-приложение из server
from server import app as application  # Импортируем `app` из `server`