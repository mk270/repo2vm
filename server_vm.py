#!/usr/bin/env python2

import sys
import os
import boto.ec2
import boto.manage.cmdshell
import time
import subprocess
from configuration import get_config


class ServerVM(object):
    class SSHCmdFailed(Exception): pass

    def __init__(self, name, git_reference):
        self.name = name
        self.git_reference = git_reference
        self.instance = None
        self.ssh = None
        self.key_file = "/home/mk270/.ssh/tmtkeys.pem"

    def run(self):
        self.instance = self.launch_instance()
        self.setup_remote_repository()

    def launch_instance(self):
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
        self.poll_until_running(reservation)
        conn.create_tags(instance.id, {"Name": self.name})
        return instance

    def poll_until_running(self, reservation):
        """Block until the instance is usable."""

        instance = reservation.instances[0]

        status = instance.update()
        while status != "running":
            print instance, status
            time.sleep(11)
            status = instance.update()

    def setup_remote_repository(self):
        repo_host = "git.unipart.io"
        cmds = [ "mkdir -p ~/.ssh",
                 "ssh-keyscan %s >> ~/.ssh/known_hosts" % repo_host,
                 "mkdir -p ~/repos"
                 ]
        for cmd in cmds:
            self.ssh_exec(cmd)

        logname = os.environ["LOGNAME"] # YES, really
        repo = "ssh://%s@%s//home/scm/hawkeye.git" % (logname, repo_host)
        self.ssh_agent_exec([ "git", "clone", repo, "repos/hawkeye" ])

        cmds = [ "git -C repos/hawkeye checkout %s" % self.git_reference ]
        for cmd in cmds:
            self.ssh_exec(cmd)

    def setup_ssh(self):
        return boto.manage.cmdshell.sshclient_from_instance(
            self.instance,
            self.key_file,
            user_name="ubuntu"
        )

    def ssh_exec(self, cmd):
        if self.ssh is None:
            self.ssh = self.setup_ssh()

        print "CMD", cmd
        status, stdout, stderr = self.ssh.run(cmd)
        if status != 0:
            print stderr
            raise SSHCmdFailed(cmd)

    def ssh_agent_exec(self, args):
        local_args = [
            "ssh", "-A", "-l", "ubuntu",
            "-i", self.key_file,
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "StrictHostKeyChecking=no",
            self.instance.ip_address
        ]
        subprocess.check_call(local_args + args)

    def ssh_example(self):
        return """To access:\n\n  ssh ubuntu@%s""" % self.instance.ip_address
