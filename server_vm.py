#!/usr/bin/env python2

import sys
import os
import json
import boto.ec2
import boto.manage.cmdshell
import time
import subprocess

class MissingEnv(Exception):
    pass

def poll_until_running(reservation):
    """Block until the instance is usable."""

    instance = reservation.instances[0]

    status = instance.update()
    while status != "running":
        print instance, status
        time.sleep(11)
        status = instance.update()

def get_env():
    def lookup_var(var):
        if var not in os.environ:
            raise MissingEnv("Missing environment variable: $%s" % var)
        return os.environ[var]

    vars = [ "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY" ]
    config_env = dict([ (k.lower(), lookup_var(k)) for k in vars ])
    return config_env

def get_config():
    """Return a dictionary of config items, from ec2.config_json and
    the $AWS_ACCESS_KEY_ID and $AWS_SECRET_ACCESS_KEY environment
    variables"""

    cwd = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(cwd, "ec2_config.json")
    config = json.load(file(config_path))

    config["security_options"] = get_env()
    return config

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

def run():
    _, name, git_reference = sys.argv
    instance = launch_instance(name)
    setup_remote_repository(instance, git_reference)

if __name__ == '__main__':
    run()
