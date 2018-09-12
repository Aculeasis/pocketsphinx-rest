#!/usr/bin/env python3

import os

import docker_starter as ds

NAME = 'mdm_terminal_2'
LAN_IP = ds.get_ip_address()
AARCH = ds.get_arch()

CFG = {
    # Имя контейнера
    'name': NAME,
    # Имя образа. userID/registry:tag
    'image': 'aculeasis/mdmt2:{}'.format(AARCH),
    # Директория сборки докера, для -b
    'docker_path': ds.WORK_DIR,
    # Путь до докерфайла, для -b
    'dockerfile': os.path.join(ds.WORK_DIR, 'Dockerfile.{}'.format(AARCH)),
    # куда монитировать volumes. ~/.docker_starter/mdm_terminal_2
    'data_path': os.path.join(ds.DATA_PATH, NAME),
    # --restart=
    'restart': 'always',
    # -p key:val (host:guest)
    'p': {7999: 7999},
    # -v key:val. Относительно 'data_path'
    'v': {
        'tts_cache': '/opt/mdmterminal2/tts_cache',
        'models': '/opt/mdmterminal2/resources/models',
        'cfg': '/opt/cfg'
    },
    # add -e key=VAL
    'e': {'HOST_REAL_IP': LAN_IP},
    # Any adding as [['-a', ' ','b'],['c', '=','d']] -> '-a b c=d'
    # 'any': [['--device', ' ', '/dev/snd'], ],
}
if ds.OS == 'linux':
    CFG['any'] = [['--device', ' ', '/dev/snd'], ]
elif ds.OS == 'windows':
    # noinspection PyTypeChecker
    CFG['e']['HOST_INTERNAL_IP'] = 'host.docker.internal'

ds.DockerStarter(CFG)
