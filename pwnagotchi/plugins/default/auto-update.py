__author__ = 'evilsocket@gmail.com'
__version__ = '1.1.0'
__name__ = 'auto-update'
__license__ = 'GPL3'
__description__ = 'This plugin checks when updates are available and applies them when internet is available.'

import os
import random
import logging
import subprocess
import requests
import platform
import shutil
import glob
import pkg_resources

import pwnagotchi
from pwnagotchi.utils import StatusFile
import pwnagotchi.ui.faces as faces

OPTIONS = dict()
READY = False
STATUS = StatusFile('/root/.auto-update')


def on_loaded():
    global READY
    if 'interval' not in OPTIONS or ('interval' in OPTIONS and OPTIONS['interval'] is None):
        logging.error("[update] main.plugins.auto-update.interval is not set")
        return
    READY = True
    logging.info("[update] plugin loaded.")


def check(version, repo, native=True):
    logging.debug("checking remote version for %s, local is %s" % (repo, version))
    info = {
        'repo': repo,
        'current': version,
        'available': None,
        'url': None,
        'native': native,
        'arch': platform.machine()
    }

    resp = requests.get("https://api.github.com/repos/%s/releases/latest" % repo)
    latest = resp.json()
    info['available'] = latest_ver = latest['tag_name'].replace('v', '')
    is_arm = info['arch'].startswith('arm')

    local = pkg_resources.parse_version(info['current'])
    remote = pkg_resources.parse_version(latest_ver)
    if remote > local:
        if not native:
            info['url'] = "https://github.com/%s/archive/%s.zip" % (repo, latest['tag_name'])
        else:
            # check if this release is compatible with arm6
            for asset in latest['assets']:
                download_url = asset['browser_download_url']
                if download_url.endswith('.zip') and (
                        info['arch'] in download_url or (is_arm and 'armhf' in download_url)):
                    info['url'] = download_url
                    break

    return info


def make_path_for(name):
    path = os.path.join("/tmp/updates/", name)
    if os.path.exists(path):
        logging.debug("[update] deleting %s" % path)
        shutil.rmtree(path, ignore_errors=True, onerror=None)
    os.makedirs(path)
    return path


def download_and_unzip(name, path, display, update):
    target = "%s_%s.zip" % (name, update['available'])
    target_path = os.path.join(path, target)

    logging.info("[update] downloading %s to %s ..." % (update['url'], target_path))
    display.update(
        force=True,
        new_data={
            'status': 'Downloading %s %s ...' % (name, update['available']),
            'face': faces.MOTIVATED
        }
    )

    os.system('wget -q "%s" -O "%s"' % (update['url'], target_path))

    logging.info("[update] extracting %s to %s ..." % (target_path, path))
    display.update(
        force=True,
        new_data={
            'status': 'Extracting %s %s ...' % (name, update['available']),
            'face': faces.EXCITED
        }
    )

    os.system('unzip "%s" -d "%s"' % (target_path, path))


def verify(name, path, source_path, display, update):
    display.update(
        force=True,
        new_data={
            'status': 'Verifying %s %s ...' % (name, update['available']),
            'face': faces.SMART
        }
    )

    checksums = glob.glob("%s/*.sha256" % path)
    if len(checksums) == 0:
        if update['native']:
            logging.warning("[update] native update without SHA256 checksum file")
            return False

    else:
        checksum = checksums[0]

        logging.info("[update] verifying %s for %s ..." % (checksum, source_path))

        with open(checksum, 'rt') as fp:
            expected = fp.read().split('=')[1].strip().lower()

        real = subprocess.getoutput('sha256sum "%s"' % source_path).split(' ')[0].strip().lower()

        if real != expected:
            logging.warning("[update] checksum mismatch for %s: expected=%s got=%s" % (source_path, expected, real))
            return False

    return True


def install(display, update):
    name = update['repo'].split('/')[1]

    path = make_path_for(name)

    download_and_unzip(name, path, display, update)

    source_path = os.path.join(path, name)
    if not verify(name, path, source_path, display, update):
        return False

    logging.info("[update] installing %s ..." % name)
    display.update(
        force=True,
        new_data={
            'status': 'Installing %s %s ...' % (name, update['available']),
            'face': faces.INTENSE
        }
    )

    if update['native']:
        dest_path = subprocess.getoutput("which %s" % name)
        if dest_path == "":
            logging.warning("[update] can't find path for %s" % name)
            return False

        logging.info("[update] stopping %s ..." % update['service'])
        os.system("service %s stop" % update['service'])
        os.system("mv %s %s" % (source_path, dest_path))
        logging.info("[update] restarting %s ..." % update['service'])
        os.system("service %s start" % update['service'])
    else:
        if not os.path.exists(source_path):
            source_path = "%s-%s" % (source_path, update['available'])

        os.system("cd %s && pip3 install ." % source_path)

    return True


def on_internet_available(agent):
    global STATUS

    config = agent.config()
    faces.load_from_config(config['ui']['faces'])

    logging.debug("[update] internet connectivity is available (ready %s)" % READY)

    if READY:
        if STATUS.newer_then_hours(OPTIONS['interval']):
            logging.debug("[update] last check happened less than %d hours ago" % OPTIONS['interval'])
            return

        logging.info("[update] checking for updates ...")

        display = agent.view()
        prev_status = display.get('status')
        prev_face = display.get('face')

        try:
            display.update(
                force=True,
                new_data={
                    'status': 'Checking for updates ...',
                    'face': random.choice(faces.LOOK_L, faces.LOOK_R)
                }
            )

            to_install = []
            to_check = [
                ('bettercap/bettercap', subprocess.getoutput('bettercap -version').split(' ')[1].replace('v', ''),
                 True, 'bettercap'),
                ('evilsocket/pwngrid', subprocess.getoutput('pwngrid -version').replace('v', ''), True, 'pwngrid-peer'),
                ('evilsocket/pwnagotchi', pwnagotchi.version, False, 'pwnagotchi')
            ]

            for repo, local_version, is_native, svc_name in to_check:
                info = check(local_version, repo, is_native)
                if info['url'] is not None:
                    logging.warning(
                        "update for %s available (local version is '%s'): %s" % (repo, info['current'], info['url']))
                    info['service'] = svc_name
                    to_install.append(info)

            num_updates = len(to_install)
            num_installed = 0

            if num_updates > 0:
                if OPTIONS['install']:
                    for update in to_install:
                        if install(display, update):
                            num_installed += 1
                else:
                    prev_status = '%d new update%c available!' % (num_updates, 's' if num_updates > 1 else '')
                    prev_face = faces.MOTIVATED

            logging.info("[update] done")

            STATUS.update()

            if num_installed > 0:
                display.update(
                    force=True,
                    new_data={
                        'status': 'Installed! Rebooting ...',
                        'face': faces.FRIEND
                    }
                )
                pwnagotchi.reboot()

        except Exception as e:
            logging.error("[update] %s" % e)

        display.update(
            force=True,
            new_data={
                'status': prev_status if prev_status is not None else '',
                'face': prev_face if prev_face is not None else faces.AWAKE
            }
        )
