#!/usr/bin/env python3

import os
from io import BytesIO

from flask import Flask, request, json
from pocketsphinx import Pocketsphinx


class PocketSphinx(Pocketsphinx):
    def decode_fp(self, fp=None, buffer_size=2048, no_search=False, full_utt=False):
        buf = bytearray(buffer_size)
        with self.start_utterance():
            while fp.readinto(buf):
                self.process_raw(buf, no_search, full_utt)
        return self


def ps_init():
    main_dir = os.path.join('/opt', 'zero_ru_cont_8k_v3')
    config = {
        'hmm': os.path.join(main_dir, 'zero_ru.cd_ptm_4000'),
        'lm': os.path.join(main_dir, 'ru.lm'),
        'dict': os.path.join(main_dir, 'ru.dic'),
    }
    return PocketSphinx(**config)


ps = ps_init()
app = Flask(__name__, static_url_path='')


@app.route('/stt', methods=['GET', 'POST'])
def say():
    if request.method == 'POST':
        target = None
        if request.headers.get('Transfer-Encoding') == 'chunked':
            target = request.stream
        elif request.data:
            target = BytesIO(request.data)

        if target is None:
            text = 'No data'
            code = 1
        else:
            text = ps.decode_fp(fp=target).hypothesis()
            code = 0
    else:
        text = 'What do you want? I accept only POST!'
        code = 2
    return json.jsonify({'text': text, 'code': code})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8085, threaded=False)
