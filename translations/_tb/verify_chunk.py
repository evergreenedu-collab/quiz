# -*- coding: utf-8 -*-
"""교재 번역 조각 검증: py translations/_tb/verify_chunk.py <ko.html> <mn.html>
- 시작태그(태그명+속성 전체)·종료태그 시퀀스가 원본과 완전히 동일해야 함 (텍스트만 달라야 함)
- 한글 잔존은 괄호 안 병기 '(서행)' 형태만 허용
- 원본의 숫자 토큰이 번역에 모두 존재해야 함
"""
import sys, re
from html.parser import HTMLParser
class P(HTMLParser):
    def __init__(s): super().__init__(convert_charrefs=False); s.seq=[]; s.text=[]
    def handle_starttag(s,t,a): s.seq.append(("S",t,tuple(sorted(a))))
    def handle_startendtag(s,t,a): s.seq.append(("SE",t,tuple(sorted(a))))
    def handle_endtag(s,t): s.seq.append(("E",t))
    def handle_data(s,d): s.text.append(d)
def parse(p):
    h=open(p,encoding="utf-8").read(); x=P(); x.feed(h); return h,x
ko_h,ko=parse(sys.argv[1]); mn_h,mn=parse(sys.argv[2])
ok=True
if ko.seq!=mn.seq:
    ok=False
    for i,(a,b) in enumerate(zip(ko.seq,mn.seq)):
        if a!=b: print(f"❌ 구조 불일치 #{i}: 원본 {a} vs 번역 {b}"); break
    else: print(f"❌ 태그 개수 불일치: 원본 {len(ko.seq)} vs 번역 {len(mn.seq)}")
else: print(f"✅ 구조 동일 (태그 {len(ko.seq)}개)")
body=re.sub(r"<script.*?</script>","",mn_h,flags=re.S)
stripped=re.sub(r"\([가-힣·,\s/~]+\)","",body)
hang=re.findall(r".{0,20}[가-힣]+.{0,20}",stripped)
if hang: ok=False; print(f"❌ 괄호 밖 한글 잔존 {len(hang)}건:", hang[:8])
else: print("✅ 괄호 밖 한글 없음")
kt=" ".join(ko.text); mt=" ".join(mn.text).replace(",","")
nums=re.findall(r"\d+(?:\.\d+)?",kt); miss=[n for n in nums if n not in mt]
if miss: ok=False; print(f"❌ 숫자 누락 {len(miss)}:", miss[:15])
else: print(f"✅ 숫자 보존 ({len(nums)}개)")
print("RESULT:", "PASS" if ok else "FAIL")
