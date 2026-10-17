"""Package this static playground without importing the bot or accessing the network."""
from pathlib import Path
import base64
import re
import zipfile

root = Path(__file__).resolve().parent
output = root.parents[2] / 'drafts' / 'widget-playground'
output.mkdir(parents=True, exist_ok=True)
fonts = (root / 'fonts.css').read_text(encoding='utf-8')
fonts = re.sub(r"url\('([^']+)'\)", lambda match: "url('data:font/woff2;base64," + base64.b64encode((root / match[1]).read_bytes()).decode('ascii') + "')", fonts)
html = (root / 'index.html').read_text(encoding='utf-8')
html = html.replace('<link rel="stylesheet" href="fonts.css">', '<style>\n' + fonts + '\n</style>')
html = html.replace('<link rel="stylesheet" href="styles.css">', '<style>\n' + (root / 'styles.css').read_text(encoding='utf-8') + '\n</style>')
html = html.replace('<script src="app.js" defer></script>', '<script defer>document.addEventListener("DOMContentLoaded", () => {\n' + (root / 'app.js').read_text(encoding='utf-8') + '\n});</script>')
html = html.replace('src="assets/avatar.png"', 'src="data:image/png;base64,' + base64.b64encode((root / 'assets/avatar.png').read_bytes()).decode('ascii') + '"')
portable = output / 'artgents-widget-playground.html'
portable.write_text(html, encoding='utf-8')
archive = output / 'artgents-widget-playground.zip'
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(root.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            bundle.write(path, 'widget-playground/' + path.relative_to(root).as_posix())
    bundle.write(portable, portable.name)
print('Portable HTML:', portable)
print('Source ZIP:', archive)
