"""Temporarily play one selected local MP4 on the paired TV."""
import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from launcher import CONFIG, request_tv, route_address

PAGE = b'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>*{box-sizing:border-box}body{margin:0;background:#000;color:white;font:22px sans-serif}video{width:100vw;height:100vh;object-fit:contain}#controls{position:fixed;bottom:0;left:0;width:100%;padding:25px 5vw 32px;background:linear-gradient(transparent,#000e);transition:opacity .4s;pointer-events:none}#track{height:10px;background:#777;border-radius:10px;overflow:hidden;margin:12px 0}#progress{height:100%;width:0;background:#fff}#times{display:flex;justify-content:space-between}#help{font-size:18px;margin-top:10px;color:#ddd}</style></head><body><video id="v" autoplay playsinline src="/video"></video><div id="controls"><div id="times"><span id="elapsed">0:00</span><span id="duration">0:00</span></div><div id="track"><div id="progress"></div></div><div id="help">OK: play / pause &nbsp; Left / Right: seek 5 seconds &nbsp; Home: exit</div></div><script>var v=document.getElementById('v'),h=document.getElementById('controls'),help=document.getElementById('help'),timer;function format(t){t=isFinite(t)?Math.floor(t):0;var s=String(t%60).padStart(2,'0'),m=Math.floor(t/60);return m+':'+s}function update(){document.getElementById('elapsed').textContent=format(v.currentTime);document.getElementById('duration').textContent=format(v.duration);document.getElementById('progress').style.width=(isFinite(v.duration)&&v.duration>0?100*v.currentTime/v.duration:0)+'%'}function show(){h.style.opacity=1;clearTimeout(timer);if(!v.paused)timer=setTimeout(function(){h.style.opacity=0},4000)}function toggle(){if(v.paused){v.play().catch(function(){help.textContent='Press OK to start playback';show()})}else v.pause()}document.addEventListener('keydown',function(e){if(e.key==='Enter'||e.keyCode===13){e.preventDefault();toggle();show()}else if(e.key==='ArrowLeft'||e.keyCode===37){e.preventDefault();v.currentTime=Math.max(0,v.currentTime-5);show()}else if(e.key==='ArrowRight'||e.keyCode===39){e.preventDefault();if(isFinite(v.duration))v.currentTime=Math.min(v.duration,v.currentTime+5);show()}});['timeupdate','loadedmetadata','play','pause','seeked'].forEach(function(e){v.addEventListener(e,update)});v.addEventListener('error',function(){help.textContent='Could not play this video. Press Home to return.';show()});v.play().catch(function(){help.textContent='Press OK to start playback';show()});show();</script></body></html>'''


def serve_video(path, config, port):
    host = config['tv_host']
    bind = route_address(host)
    size = path.stat().st_size
    media_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.client_address[0] != host or self.path not in ('/', '/video'):
                self.send_error(404); return
            if self.path == '/':
                self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(PAGE))); self.end_headers(); self.wfile.write(PAGE); return
            start, end = 0, size - 1
            value = self.headers.get('Range')
            if value:
                try:
                    unit, spec = value.split('=', 1); a, b = spec.split('-', 1)
                    if unit != 'bytes' or not a or ',' in b: raise ValueError()
                    start = int(a); end = min(int(b), end) if b else end
                    if start < 0 or start > end or start >= size: raise ValueError()
                except ValueError:
                    self.send_response(416); self.send_header('Content-Range', 'bytes */%d' % size); self.end_headers(); return
            self.send_response(206 if value else 200)
            self.send_header('Content-Type', media_type); self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(end-start+1))
            if value: self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, end, size))
            self.end_headers()
            try:
                with path.open('rb') as f:
                    f.seek(start); remaining = end-start+1
                    while remaining:
                        part = f.read(min(65536, remaining))
                        if not part: break
                        self.wfile.write(part); remaining -= len(part)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, fmt, *args):
            pass

    server = ThreadingHTTPServer((bind, port), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        request_tv(host, '/app/launch', config['auth_token'], {'VALUE': {'NAME_SPACE': 4, 'APP_ID': '3001',
                   'MESSAGE': 'http://%s:%d/' % (bind, port)}})
        print('Video opened. Press Home on the TV to leave; Ctrl+C here stops serving.', flush=True)
        while True:
            threading_event.wait(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    import threading
    threading_event = threading.Event()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path, help='path to a local video file')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--config', type=Path, default=CONFIG, help='paired launcher configuration (default: config.json)')
    args = parser.parse_args()
    path = args.file.expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in ('.mp4', '.m4v', '.webm'):
        parser.error('Select an existing MP4, M4V, or WebM file')
    if not args.config.exists():
        parser.error('Pair first using launcher.py')
    serve_video(path, json.loads(args.config.read_text(encoding='utf-8')), args.port)
