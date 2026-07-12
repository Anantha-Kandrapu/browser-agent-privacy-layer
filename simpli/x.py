import base64
import json
import sys

path = sys.argv[1]
encoded = base64.b64encode(open(path, 'rb').read()).decode('ascii')
print(json.dumps({'id': '1', 'image': encoded, 'mode': 'accurate'}))

# python3 x.py image-2.png | /tmp/vision_ocr_worker | jq .