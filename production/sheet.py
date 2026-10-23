import sys
from PIL import Image
# 用法：python3 sheet.py CH 秒 ...（先 CH=N node render.js still 秒 ...）
ch, ts = sys.argv[1], sys.argv[2:]
ims = [Image.open(f'build/still{ch}_{t}.png').convert('RGB').resize((360, 640)) for t in ts]
cols = min(5, len(ims)); rows = (len(ims) + cols - 1) // cols
sh = Image.new('RGB', (cols * 364, rows * 644), (30, 30, 30))
for i, im in enumerate(ims): sh.paste(im, ((i % cols) * 364, (i // cols) * 644))
sh.save(f'build/sheet{ch}.jpg', quality=88); print(sh.size)
