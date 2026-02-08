import http.server
import io
import os
import glob
import threading
import urllib.parse
import time
from inky.auto import auto
from PIL import Image

# Initialize Inky
inky = auto()
inky_lock = threading.Lock()

IMG_DIR = "img"
if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

def update_inky_task(img_bytes):
    with inky_lock:
        try:
            img = Image.open(io.BytesIO(img_bytes))
            inky.set_image(img)
            inky.show()
        except Exception as e:
            print(f"Async Update Error: {e}")

def get_gallery_html():
    files = glob.glob(os.path.join(IMG_DIR, "*.png"))
    files.sort(key=os.path.getmtime, reverse=True)
    
    html = '<div class="gallery">'
    for f in files:
        name = os.path.basename(f)
        html += f'''
        <div class="item" onclick="reloadImage('{name}')">
            <img src="/{f}" loading="lazy">
            <div class="item-meta">{name}</div>
            <div class="overlay">PUSH TO SCREEN</div>
        </div>'''
    html += '</div>'
    return html

def get_full_html():
    is_busy = "true" if inky_lock.locked() else "false"
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Inky Dash</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            :root {{ --accent: #00ff88; --bg: #121212; --card: #1e1e1e; }}
            body {{ font-family: system-ui, sans-serif; background: var(--bg); color: white; margin: 0; padding: 20px; }}
            .container {{ max-width: 1000px; margin: 0 auto; }}
            
            .header-card {{ background: var(--card); padding: 2rem; border-radius: 16px; border: 1px solid #333; text-align: center; margin-bottom: 2rem; }}
            .status {{ margin-bottom: 1rem; font-size: 0.9rem; display: flex; align-items: center; justify-content: center; gap: 8px; }}
            .dot {{ width: 8px; height: 8px; border-radius: 50%; background: #555; }}
            .dot.busy {{ background: #ff4444; box-shadow: 0 0 8px #ff4444; }}
            .dot.idle {{ background: var(--accent); box-shadow: 0 0 8px var(--accent); }}

            .gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }}
            .item {{ background: var(--card); border-radius: 12px; overflow: hidden; border: 1px solid #333; cursor: pointer; position: relative; transition: 0.2s; }}
            .item:hover {{ border-color: var(--accent); transform: translateY(-4px); }}
            .item img {{ width: 100%; display: block; filter: grayscale(0.2); }}
            .item-meta {{ padding: 10px; font-size: 0.8rem; color: #888; text-align: center; }}
            
            .overlay {{ position: absolute; inset: 0; background: rgba(0,255,136,0.15); display: flex; align-items: center; justify-content: center; opacity: 0; transition: 0.2s; font-weight: bold; color: var(--accent); text-shadow: 0 2px 4px rgba(0,0,0,0.5); }}
            .item:hover .overlay {{ opacity: 1; }}

            #toast {{ position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: var(--accent); color: black; padding: 12px 24px; border-radius: 30px; font-weight: bold; opacity: 0; transition: 0.3s; pointer-events: none; z-index: 100; }}
            #toast.show {{ opacity: 1; bottom: 40px; }}

            input[type="file"] {{ margin: 1rem 0; color: #888; }}
            .btn {{ background: var(--accent); color: black; border: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; max-width: 300px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-card">
                <h2>Inky Impression Control</h2>
                <div class="status">
                    <div id="status-dot" class="dot"></div>
                    <span id="status-text">Checking status...</span>
                </div>
                <form method="POST" enctype="multipart/form-data">
                    <input type="file" name="file" accept="image/png" required><br>
                    <input type="submit" value="UPLOAD NEW IMAGE" class="btn">
                </form>
            </div>

            <h3 style="color: #666; text-transform: uppercase; letter-spacing: 1px; font-size: 0.8rem;">Recent History</h3>
            {get_gallery_html()}
        </div>

        <div id="toast">Updating Display...</div>

        <script>
            function showToast(msg) {{
                const t = document.getElementById('toast');
                t.innerText = msg;
                t.classList.add('show');
                setTimeout(() => t.classList.remove('show'), 3000);
            }}

            function reloadImage(name) {{
                showToast("Reloading " + name + "...");
                const data = new URLSearchParams();
                data.append('filename', name);
                
                fetch('/reload', {{ method: 'POST', body: data }})
                .then(res => {{
                    if(res.ok) updateStatus();
                }});
            }}

            function updateStatus() {{
                fetch('/status').then(r => r.json()).then(data => {{
                    const dot = document.getElementById('status-dot');
                    const txt = document.getElementById('status-text');
                    if(data.busy) {{
                        dot.className = 'dot busy';
                        txt.innerText = 'Screen is BUSY';
                    }} else {{
                        dot.className = 'dot idle';
                        txt.innerText = 'Screen is IDLE';
                    }}
                }});
            }}

            // Poll status every 5 seconds
            setInterval(updateStatus, 5000);
            updateStatus();
        </script>
    </body>
    </html>
    """

class InkyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            busy = "true" if inky_lock.locked() else "false"
            self.wfile.write(f'{{"busy": {busy}}}'.encode())
            return

        if self.path.startswith("/img/"):
            try:
                with open(self.path[1:], "rb") as f:
                    self.send_response(200)
                    self.send_header("Content-type", "image/png")
                    self.end_headers()
                    self.wfile.write(f.read())
                return
            except:
                self.send_error(404)
                return

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(get_full_html().encode())

    def do_POST(self):
        if self.path == "/reload":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            params = urllib.parse.parse_qs(post_data)
            filename = params.get('filename', [None])[0]
            
            if filename:
                with open(os.path.join(IMG_DIR, filename), "rb") as f:
                    img_bytes = f.read()
                    threading.Thread(target=update_inky_task, args=(img_bytes,), daemon=True).start()
            
            self.send_response(204)
            self.end_headers()
            return

        # New Uploads
        content_length = int(self.headers['Content-Length'])
        boundary = self.headers.get_boundary().encode()
        raw_data = self.rfile.read(content_length)
        parts = raw_data.split(boundary)
        for part in parts:
            if b'Content-Type: image/png' in part:
                header_end = part.find(b'\r\n\r\n') + 4
                footer_start = part.rfind(b'\r\n')
                img_bytes = part[header_end:footer_start]
                
                next_name = os.path.join(IMG_DIR, f"img_{int(time.time())}.png")
                with open(next_name, "wb") as f:
                    f.write(img_bytes)
                
                threading.Thread(target=update_inky_task, args=(img_bytes,), daemon=True).start()
                
                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()
                return

if __name__ == "__main__":
    server = http.server.HTTPServer(('0.0.0.0', 8000), InkyHandler)
    print("Inky Dash running on http://<pi-ip>:8000")
    server.serve_forever()