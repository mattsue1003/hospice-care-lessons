#!/bin/zsh
# 依序算出 5 課：cues → mix → frames → mux（含網頁版）
cd ${0:a:h}
for c in ${@:-1 2 3 4 5}; do
  CH=$c node render.js cues && python3 build.py mix $c && rm -rf build/ch$c && CH=$c node render.js frames 6 && python3 build.py mux $c || exit 1
done
