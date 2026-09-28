from pathlib import Path
import json
R=Path(__file__).parent
text=(R/'static/index.template.html').read_text(encoding='utf-8')
for marker,fn in [('STYLE','style.css'),('YTCORE','youtube-core.js'),('AUTOCORE','auto-lessons.js'),('KOCORE','korean-core.js'),('CORE','core.js'),('SPEECHCORE','speech-check.js'),('CATALOGCORE','material-catalog.js'),('APP','app.js'),('YTAPP','youtube.js'),('AUTOAPP','auto-youtube.js'),('KOAPP','korean-practice.js'),('SCRIPTAPP','transcript-player.js'),('MATERIALAPP','materials.js')]:text=text.replace('/*'+marker+'*/',(R/'static'/fn).read_text(encoding='utf-8'))
for marker,fn in [('DATA','library.json'),('EXERCISES','exercises.json'),('TRANSFER','transfer.json'),('MATERIALS','materials.json'),('VIDEO_MATERIALS','video-materials.json')]:
 raw=json.dumps(json.loads((R/'data'/fn).read_text(encoding='utf-8')),ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
 text=text.replace('/*'+marker+'*/',raw)
(R/'static/index.html').write_text(text,encoding='utf-8')
(R/'OPEN_ME.html').write_text(text,encoding='utf-8')
print('Built standalone + server HTML:',len(text),'chars')
