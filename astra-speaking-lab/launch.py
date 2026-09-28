from pathlib import Path
import os,sys,threading,webbrowser,socket
from dotenv import load_dotenv
load_dotenv(Path(__file__).with_name('.env'))
port=int(os.getenv('PORT','8765'))
s=socket.socket()
try:s.bind(('127.0.0.1',port))
except OSError:
    print(f'Port {port} is already in use. Close the previous instance or change PORT in .env.')
    sys.exit(1)
finally:s.close()
if os.getenv('ASTRA_NO_BROWSER') != '1':
    threading.Timer(1.5,lambda:webbrowser.open(f'http://127.0.0.1:{port}')).start()
print(f'Open http://127.0.0.1:{port}  |  Ctrl+C stops the server.')
import uvicorn
from server import app
uvicorn.run(app,host='127.0.0.1',port=port,log_level='warning')
