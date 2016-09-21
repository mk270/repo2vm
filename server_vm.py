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

    def __init__(self, name, git_reference, key_file, conf_file):
        self.name = name
        self.git_reference = git_reference
        self.instance = None
        self.ssh = None
        self.key_file = key_file

        self.config = get_config(conf_file)
        self.remote_username = self.config["user_name"]
        self.repo_host = self.config["repo_host"]
        self.repo_path = self.config["repo_path"]

    def run(self):
        self.instance = self.launch_instance()
        self.setup_remote_repository()

    def launch_instance(self):
        """Create an instance, wait for it to come up, and tag it with a name"""

        security_options = self.config["security_options"]
        region = self.config["region"]

        conn = boto.ec2.connect_to_region(region, **security_options)
        reservation = conn.run_instances(
            self.config["ami_id"],
            key_name=self.config["key_name"],
            security_groups=self.config["security_groups"]
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

    def _tidy_repo_name(self, repo_name):
        if "/" in repo_name:
            repo_name = repo_name.split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        return repo_name

    def setup_remote_repository(self):
        cmds = [ "mkdir -p ~/.ssh",
                 "ssh-keyscan %s >> ~/.ssh/known_hosts" % self.repo_host,
                 "mkdir -p ~/repos"
                 ]
        for cmd in cmds:
            self.ssh_exec(cmd)

        tidy_repo = self._tidy_repo_name(self.repo_path)
        repo_dir = "repos/" + tidy_repo

        logname = os.environ["LOGNAME"] # YES, really
        repo = "ssh://%s@%s%s" % (logname, self.repo_host, self.repo_path)
        self.ssh_agent_exec([ "git", "clone", repo, repo_dir ])

        cmds = [ "git -C repos/hawkeye checkout %s" % self.git_reference ]
        for cmd in cmds:
            self.ssh_exec(cmd)

    def setup_ssh(self):
        return boto.manage.cmdshell.sshclient_from_instance(
            self.instance,
            self.key_file,
            user_name=self.remote_username
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
            "ssh", "-A", "-l", self.remote_username,
            "-i", self.key_file,
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "StrictHostKeyChecking=no",
            self.instance.ip_address
        ]
        subprocess.check_call(local_args + args)

    def ssh_example(self):
        return """To access:\n\n  ssh -i %s %s@%s""" % (
            self.key_file, self.remote_username, self.instance.ip_address
        )
