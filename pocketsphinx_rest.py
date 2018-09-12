#!/usr/bin/env python3

import os

import docker_starter.docker_starter as ds

NAME = 'pocketsphinx_rest'
AARCH = ds.get_arch()

CFG = {
    'name': NAME,
    'image': 'aculeasis/pocketsphinx-rest:{}'.format(AARCH),
    'docker_path': ds.WORK_DIR,
    'dockerfile': os.path.join(ds.WORK_DIR, 'Dockerfile.{}'.format(AARCH)),
    'data_path': os.path.join(ds.DATA_PATH, NAME),
    'restart': 'always',
    'p': {8085: 8085}
}

ds.DockerStarter(CFG)
