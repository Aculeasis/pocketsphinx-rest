import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import platform

WORK_DIR = os.path.abspath(sys.path[0])
HOME_DIR = os.path.expanduser('~')
DATA_PATH = os.path.join(HOME_DIR, '.docker_starter')
OS = platform.uname()[0].lower()
OS = 'linux' if OS.startswith('linux') else OS


def get_ip_address():
    s = socket.socket(type=socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    return s.getsockname()[0]


def get_arch() -> str:
    aarch = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64v8', 'armv7l': 'arm32v7'}
    return aarch.get(platform.uname()[4].lower(), 'unknown')


def __request_handler(url, headers, use_info=False) -> dict:
    request = urllib.request.Request(url=url, headers=headers)
    try:
        response = urllib.request.urlopen(request)
    except urllib.error.HTTPError as e:
        print('Request failed: {}'.format(e.reason))
        return {}
    except urllib.error.URLError as e:
        print('Request connection failed: {}'.format(e.reason))
        return {}
    if response.getcode() != 200:
        print('Request code error: {}'.format(response.getcode()))
        return {}
    response_text = response.read().decode('utf-8') if not use_info else \
        response.info().as_string().strip('\n').split('\n')
    try:
        if not use_info:
            result = json.loads(response_text)
        else:
            result = {}
            for line in response_text:
                key, val = line.split(': ', 1)
                result[key] = val
    except (json.JSONDecodeError, ValueError) as e:
        print('Decode error {}'.format(e))
        return {}
    return result


def __docker_auth(registry: str, headers: dict):
    params = {'service': 'registry.docker.io', 'scope': 'repository:{}:pull'.format(registry)}
    url = 'https://auth.docker.io/token?{}'.format('&'.join(['{}={}'.format(key, val) for key, val in params.items()]))
    token = __request_handler(url, headers).get('token')
    if token is None:
        print('Auth error - no token')
    return token


def _docker_remote_sha256(rep_tag: str):
    registry, tag = rep_tag.rsplit(':', 1)
    headers = {'Accept': 'application/vnd.docker.distribution.manifest.v2+json'}
    token = __docker_auth(registry, headers)
    if token is None:
        return None
    headers['Authorization'] = 'Bearer {}'.format(token)
    url = 'https://registry-1.docker.io/v2/{}/manifests/{}'.format(registry, tag)
    sha256 = __request_handler(url, headers, True).get('Docker-Content-Digest')
    if sha256 is None:
        print('Registry error headers parsing - sha256 not found')
    return sha256


def _docker_run_fatal(cmd: list, fatal: bool = False, stderr=subprocess.PIPE, stdout=subprocess.PIPE):
    run = subprocess.run(['docker', ] + cmd, stderr=stderr, stdout=stdout)
    if run.returncode:
        if fatal:
            raise RuntimeError('Error docker {}: {}'.format(' '.join(cmd), run.stderr.decode()))
    return run


def _docker_test() -> bool:
    return not _docker_run_fatal(['ps', ]).returncode


def _docker_stop(name: str) -> bool:
    return not _docker_run_fatal(['stop', name]).returncode


def _docker_start(name: str) -> bool:
    return not _docker_run_fatal(['start', name]).returncode


def _docker_rm(name: str) -> bool:
    return not _docker_run_fatal(['rm', name]).returncode


def _docker_rmi(rep_tag: str) -> bool:
    return not _docker_run_fatal(['rmi', rep_tag]).returncode


def _docker_pull(rep_tag: str) -> bool:
    # noinspection PyTypeChecker
    return not _docker_run_fatal(cmd=['pull', rep_tag], stdout=None, stderr=None).returncode


def _docker_build(rep_tag: str, file: str, path: str) -> bool:
    cmd = ['build', '--rm', '--no-cache', '-t', rep_tag, '-f', file, path]
    # noinspection PyTypeChecker
    return not _docker_run_fatal(cmd=cmd, stdout=None, stderr=None).returncode


def _docker_run(cmd: list) -> bool:
    # noinspection PyTypeChecker
    return not _docker_run_fatal(cmd=['run', ] + cmd, stderr=None).returncode


def _docker_image_id_from_container(name):
    run = _docker_run_fatal(['ps', '-a', '--format', '{{.Names}} {{.Image}}'], True)
    for line in run.stdout.decode().strip('\n').split('\n'):
        data = line.split(' ')
        if len(data) == 2 and data[0] == name:
            return data[1]
    return None


def _docker_repo_id() -> set:
    run = _docker_run_fatal(['images', '--format', '{{.ID}}'], True)
    return {line for line in run.stdout.decode().strip('\n').rsplit('\n')}


class DockerStarter:
    def __init__(self, cfg: dict or list, unit_name: str or None=None):
        self._cfg = cfg if type(cfg) is list else [cfg, ]
        self._args, install = self._cli_parse(self._allow_b())
        self._check()
        if install is not None:
            SystemD(install, unit_name or self._cfg[0]['name'])
            return
        if self._args.t:
            [run.join() for run in [_StarterWorker(cfg, self._args) for cfg in self._cfg]]
        else:
            [_StarterWorker(cfg, self._args).join() for cfg in self._cfg]

    def _allow_b(self):
        allow = False
        for cfg in self._cfg:
            allow |= os.path.isdir(cfg.get('docker_path', '')) and os.path.isfile(cfg.get('dockerfile', ''))
        return allow

    def _check(self):
        if OS != 'linux':
            print('Warning! OS {} partial support.'.format(OS))
        if not _docker_test():
            print('Docker not installed or not enough privileges')
            print('Install docker or use sudo')
            exit(1)
        images = set()
        names = set()
        for cfg in self._cfg:
            if cfg['name'] in names:
                print('Container name {} duplicated. It must be unique. UNACCEPTABLE!'.format(cfg['name']))
                exit(1)
            names.add(cfg['name'])
            if self._args.t and cfg['image'] in images:
                print('Image {} duplicated and threading enabled, don\'t use -t. UNACCEPTABLE!'.format(cfg['image']))
                exit(1)
            images.add(cfg['image'])

    @staticmethod
    def _cli_parse(allow_b):
        def key_val(string):
            data = string.split('=', 1)
            if len(data) != 2:
                print('Bad argument -e {}, use -e KEY=VAL'.format(string))
                exit(1)
            return data
        parser = argparse.ArgumentParser()
        one = parser.add_mutually_exclusive_group(required=True)
        one.add_argument('--start', action='store_true', help='Start container')
        one.add_argument('--stop', action='store_true', help='Stop container')
        one.add_argument('--update', action='store_true', help='Check image update')
        one.add_argument('--upgrade', action='store_true', help='Upgrade image and re-create container')
        one.add_argument('--remove', action='store_true', help='Remove container and image')
        one.add_argument('--purge', action='store_true', help='Remove container, image and data')
        one.add_argument('--restart', action='store_true', help='Run --stop && --start')

        parser.add_argument('-e', action='append', type=key_val, metavar='KEY=VAL', help='Add more env')
        if allow_b and OS != 'windows':
            parser.add_argument('-b', action='store_true', help='Build images from Dockerfile, no pull from hub')
        parser.add_argument('-t', action='store_true', help='Threaded works (Dangerous)')
        parser.add_argument('-f', action='store_true', help='Allow upgrade image from other source (hub or -b)')
        if OS == 'linux':
            two = parser.add_mutually_exclusive_group()
            two.add_argument('--install', action='store_true', help='Install systemd unit')
            one.add_argument('--uninstall', action='store_true', help='Remove systemd unit')
        install = None
        args = parser.parse_args()
        if vars(args).get('uninstall'):
            install = False
        elif vars(args).get('install'):
            install = True
        return args, install


class _StarterWorker(threading.Thread):
    def __init__(self, cfg: dict, cli):
        super().__init__()
        self._cfg = cfg
        self._cli = cli
        self.start()

    def run(self):
        if not self._config_check():
            pass
        elif self._cli.start:
            self._c_start()
        elif self._cli.stop:
            self._c_stop()
        elif self._cli.update:
            self._c_update()
        elif self._cli.upgrade:
            self._c_upgrade()
        elif self._cli.remove:
            self._c_remove()
        elif self._cli.purge:
            self._c_purge()
        elif self._cli.restart:
            if self._c_stop():
                self._c_start()

    def _config_check(self):
        for key in ['name', 'image', 'data_path']:
            if key not in self._cfg:
                print('\'{}\' must be present'.format(key))
                return False
        type_check = {
            str: ['name', 'image', 'data_path', 'dockerfile', 'docker_path', 'restart'],
            dict: ['p', 'v', 'e'],
            list: ['any', ]
        }
        for key in type_check:
            for opt in type_check[key]:
                if opt in self._cfg and not isinstance(self._cfg[opt], key):
                    print('Option \'{}\' must be {}, not {}'.format(opt, key.__name__, type(self._cfg[opt]).__name__))
                    return False
        return True

    def _c_start(self):
        if _docker_image_id_from_container(self._cfg['name']):
            result = '' if _docker_start(self._cfg['name']) else 'Failed '
            return print('{}start {}'.format(result, self._cfg['name']))
        if self._get_image_data()['id'] is None and not self._pull():
            return print('Runtime error, exit.')
        self._run()

    def _c_stop(self) -> bool:
        if _docker_image_id_from_container(self._cfg['name']):
            if _docker_stop(self._cfg['name']):
                print('stop {}'.format(self._cfg['name']))
            else:
                print('Error stopping {}'.format(self._cfg['name']))
                return False
        elif self._cli.stop:
            print('Container {} not found.'.format(self._cfg['name']))
        return True

    def _c_update(self, old: dict or None = None):
        old = old or self._get_image_data()
        if old['sha256'] is None:
            if self._cli.update:
                print('Local {} not found. Use --start'.format(self._cfg['image']))
            return True
        new_sha = _docker_remote_sha256(self._cfg['image'])
        if new_sha is None:
            return False
        got_name = self._cfg['image']
        if old['name'] != got_name:
            got_name = '{} ({})'.format(old['name'], got_name)
        if old['sha256'] == new_sha:
            print('{} up to date'.format(got_name))
            return False
        else:
            if self._cli.update:
                msg = '. You build image? Use -b, -f for force pull' if old['sha256'] == '<none>' else ''
                print('{} update found. Use --upgrade{}'.format(got_name, msg))
            return True

    def _c_upgrade(self):
        old = self._get_image_data()
        if old['sha256'] is None:
            return self._c_start()
        if old['id'] is None:
            return print('Runtime error,{} ID not found, exit'.format(self._cfg['image']))
        if not self._allow_source_change(old['sha256']):
            return
        if not (self._c_update(old) or vars(self._cli).get('b', False)):
            return
        if not self._pull():
            return print('Runtime error, exit')
        if self._c_stop() and self._rm():
            self._run()
        self._rmi(old)

    def _allow_source_change(self, old_sha):
        # Переключится с хаба на локальные сборки или обратно можно только с -f
        sources = ['hub', 'local build']
        old = sources[0] if old_sha != '<none>' else sources[1]
        new = sources[0] if not vars(self._cli).get('b', False) else sources[1]
        if old != new and not self._cli.f:
            print('Disallow! Use -f for change image source from {} to {}'.format(old, new))
            return False
        return True

    def _pull(self):
        if vars(self._cli).get('b', False):
            return _docker_build(self._cfg['image'], self._cfg['dockerfile'], self._cfg['docker_path'])
        else:
            return _docker_pull(self._cfg['image'])

    def _c_remove(self):
        data = self._get_image_data()
        result = self._c_stop() and self._rm()
        self._rmi(data)
        return result

    def _rm(self):
        if _docker_image_id_from_container(self._cfg['name']):
            return _docker_rm(self._cfg['name'])
        return True

    @staticmethod
    def _rmi(data: dict) -> bool:
        if data['id'] in _docker_repo_id():
            if not _docker_rmi(data['id']):
                print('Error delete {name} ({id}) image. Maybe containers use it?'.format(**data))
                return False
        return True

    def _c_purge(self):
        if self._c_remove():
            shutil.rmtree(self._cfg['data_path'], ignore_errors=True)

    def _get_image_data(self) -> dict:
        id_ = _docker_image_id_from_container(self._cfg['name'])
        run = _docker_run_fatal(
            ['images', '--digests', '--format', '{{.Repository}}:{{.Tag}} {{.ID}} {{.Digest}}'],
            True
        )
        if id_ == self._cfg['image']:
            id_ = None
        for line in run.stdout.decode().strip('\n').split('\n'):
            data = line.split(' ')
            if len(data) != 3:
                continue
            if id_ and id_ == data[1]:
                return {'name': data[0], 'id': data[1], 'sha256': data[2]}
            elif not id_ and data[0] == self._cfg['image']:
                return {'name': data[0], 'id': data[1], 'sha256': data[2]}
        return {'name': None, 'id': None, 'sha256': None}

    def _run(self):
        cmd = ['-d', ]
        for key, val in self._cfg.get('p', {}).items():
            cmd.extend(['-p', '{}:{}'.format(key, val)])

        for key, val in self._cfg.get('v', {}).items():
            mount_path = os.path.join(self._cfg['data_path'], key)
            os.makedirs(mount_path, exist_ok=True)
            cmd.extend(['-v', '{}:{}'.format(mount_path, val)])

        if self._cli.e is not None:
            for env in self._cli.e:
                if 'e' not in self._cfg:
                    self._cfg['e'] = {}
                self._cfg['e'][env[0]] = env[1]

        for key, val in self._cfg.get('e', {}).items():
            cmd.extend(['-e', '{}={}'.format(key, val)])

        for el in self._cfg.get('any', []):
            if el[1] == ' ':
                cmd.extend([el[0], el[2]])
            else:
                cmd.append('{}{}{}'.format(*el))

        cmd.append('--restart={}'.format(self._cfg.get('restart', 'always')))
        cmd.extend(['--name', self._cfg['name']])
        cmd.append(self._cfg['image'])

        result = _docker_run(cmd)
        msg = 'docker run' if result else 'Failed docker run'
        print('{} {}'.format(msg, ' '.join(cmd)))
        return result


class SystemD:
    def __init__(self, action, name):
        self._root_test()
        name = '{} auto'.format(name)
        f_name = '_'.join(name.lower().split())
        self._files = ['{}.service'.format(f_name), '{}.timer'.format(f_name)]
        self._systemd_path = '/etc/systemd/system/'
        self._path = {
            '_TIME_': '6h',
            '_PARAMS_': self._get_params_str(),
            '_MAIN_': os.path.abspath(sys.argv[0]),
            '_NAME_': name
        }
        self._data = {k: self._getter(k) for k in self._files}
        if action is None:
            raise RuntimeError('Action is None')
        elif action:
            self.install()
        else:
            self.uninstall()

    def install(self):
        for k in self._data:
            path = os.path.join(self._systemd_path, k)
            with open(path, 'w') as fp:
                fp.write(self._data[k])
        self._systemd_reload()
        self._systemd_enable()

    def uninstall(self):
        self._systemd_disable()
        for k in self._data:
            try:
                os.remove(os.path.join(self._systemd_path, k))
            except FileNotFoundError:
                pass
        self._systemd_reload()

    @staticmethod
    def _get_params_str() -> str:
        params = sys.argv[1:]
        for rm in ['--install', '--uninstall']:
            if rm in params:
                params.remove(rm)
        return ' '.join(params)

    @staticmethod
    def _root_test():
        if os.geteuid() != 0:
            print('--(un)install need root privileges. Use sudo, bye.')
            exit(1)

    @staticmethod
    def _systemd_reload():
        subprocess.run(['systemctl', 'daemon-reload'])

    def _systemd_enable(self):
        subprocess.run(['systemctl', 'enable', self._files[1]])
        subprocess.run(['systemctl', 'start', self._files[1]])

    def _systemd_disable(self):
        subprocess.run(['systemctl', 'stop', self._files[1]])
        subprocess.run(['systemctl', 'disable', self._files[1]])

    def _getter(self, file: str) -> str:
        d = {
            self._files[0]: [
                '[Unit]',
                'Description={_NAME_} job',
                '',
                '[Service]',
                'Type=oneshot',
                'ExecStart=/usr/bin/python3 -u {_MAIN_} {_PARAMS_}'
            ],
            self._files[1]: [
                '[Unit]',
                'Description={_NAME_}',
                '',
                '[Timer]',
                'OnBootSec=15min',
                'OnUnitActiveSec={_TIME_}',
                '',
                '[Install]',
                'WantedBy=timers.target'
            ]
        }
        return '\n'.join(d[file]).format(**self._path)
