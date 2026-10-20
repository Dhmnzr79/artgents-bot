"""No provider/browser required for actual catalog callbacks and composer navigation."""
from pathlib import Path
import shutil
import subprocess


def test_catalog_question_callbacks_offline():
    root=Path(__file__).resolve().parents[1]
    node=shutil.which('node') or r'C:\Program Files\nodejs\node.exe'
    result=subprocess.run([node,str(root/'tests/js/widget_catalog_question_test.mjs')],cwd=root,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
