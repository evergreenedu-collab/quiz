# -*- coding: utf-8 -*-
"""로컬 검증용 정적 서버.
사용법: py serve.py  → 브라우저에서 http://localhost:8000/ 접속
이미지·동영상 상대경로와 PWA 동작을 로컬에서 확인한다.
"""
import http.server
import socketserver
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
PORT = 8000
Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"로컬 서버 실행 중: http://localhost:{PORT}/")
    print("  한국어: http://localhost:8000/index.html")
    print("  영어:   http://localhost:8000/en.html")
    print("  중국어: http://localhost:8000/cn.html")
    print("  베트남어: http://localhost:8000/vn.html")
    print("종료하려면 Ctrl+C")
    httpd.serve_forever()
