#!/usr/bin/env python2

import sys
import os
import boto.ec2
import boto.manage.cmdshell
import time
import subprocess
from configuration import get_config

def poll_until_running(reservation):
    """Block until the instance is usable."""

    instance = reservation.instances[0]

    status = instance.update()
    while status != "running":
        print instance, status
        time.sleep(11)
        status = instance.update()

def launch_instance(name):
    """Create an instance, wait for it to come up, and tag it with a name"""

    config = get_config()
    security_options = config["security_options"]
    conn = boto.ec2.connect_to_region(config["region"], **security_options)
    reservation = conn.run_instances(
        config["ami_id"],
        key_name=config["key_name"],
        security_groups=config["security_groups"]
    )

    instance = reservation.instances[0]
    poll_until_running(reservation)
    conn.create_tags(instance.id, {"Name": name})
    return instance

def setup_remote_repository(instance, git_reference):
    key_file = "/home/mk270/.ssh/tmtkeys.pem"
    cmds = [ "mkdir -p ~/.ssh",
             "ssh-keyscan git.unipart.io >> ~/.ssh/known_hosts",
             "mkdir -p ~/repos"
             ]
    ssh = boto.manage.cmdshell.sshclient_from_instance(
        instance,
        key_file,
        user_name="ubuntu")
    for cmd in cmds:
        print "CMD", cmd
        status, stderr, stdout = ssh.run(cmd)
        assert status == 0

    logname = os.environ["LOGNAME"] # YES, really
    repo = "ssh://%s@git.unipart.io//home/scm/hawkeye.git" % logname

    subprocess.check_call([
        "ssh", "-A", "-l", "ubuntu",
        "-i", key_file,
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "StrictHostKeyChecking=no",
        instance.ip_address,
        "git", "clone", repo, "repos/hawkeye"
    ])

    cmds = [ "git -C repos/hawkeye checkout %s" % git_reference ]
    for cmd in cmds:
        print "CMD", cmd
        status, stderr, stdout = ssh.run(cmd)
        assert status == 0

class ServerVM(object):
    def __init__(self, name, git_reference):
        self.name = name
        self.git_reference = git_reference

    def run(self):
        instance = launch_instance(self.name)
        setup_remote_repository(instance, self.git_reference)
