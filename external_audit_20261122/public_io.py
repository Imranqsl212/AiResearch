"""Small read-only public artifact client. Never imports downloaded code."""
import hashlib
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parent
BUCKET = 'https://swe-bench-submissions.s3.amazonaws.com'


def fetch(url):
    """Keep the raw payload (and its original hash) outside deliverables."""
    if not url.startswith('https://'):
        raise ValueError(url)
    cache = Path(tempfile.gettempdir()) / 'swe_public_io_20261122'
    cache.mkdir(exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()
    path = cache / key
    if not path.exists():
        with tempfile.NamedTemporaryFile(dir=cache, delete=False) as file:
            tmp = Path(file.name)
        try:
            subprocess.run(['curl', '-fsSL', '--retry', '2', '--max-time', '240',
                            '--max-filesize', '150000000', '-o', str(tmp), url], check=True)
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
    raw = path.read_bytes()
    return raw, {'url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def list_s3(prefix):
    params = {'list-type': '2', 'prefix': prefix}
    keys = []
    while True:
        data, _ = fetch(BUCKET+'/?'+urlencode(params))
        xml = ET.fromstring(data)
        keys.extend(k.text for k in xml.findall('.//{*}Contents/{*}Key'))
        token = xml.findtext('{*}NextContinuationToken')
        if not token:
            return keys
        params['continuation-token'] = token


def get_key(key):
    return fetch(BUCKET+'/'+quote(key,safe='/'))
