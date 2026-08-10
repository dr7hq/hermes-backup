#!/usr/bin/env python3
"""
Simple web server for personal website.
Serves the static HTML file on Railway.
"""
from flask import Flask, send_file
import os

app = Flask(__name__)

@app.route('/')
def index():
    return send_file('/data/workspace/website/index.html')

@app.route('/health')
def health():
    return {'status': 'ok'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"🌐 Website running on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
