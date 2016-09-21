
import os
import json

class MissingEnv(Exception):
    pass

def get_env():
    def lookup_var(var):
        if var not in os.environ:
            raise MissingEnv("Missing environment variable: $%s" % var)
        return os.environ[var]

    vars = [ "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY" ]
    config_env = dict([ (k.lower(), lookup_var(k)) for k in vars ])
    return config_env

def get_config(conf_file):
    """Return a dictionary of config items, from ec2.config_json and
    the $AWS_ACCESS_KEY_ID and $AWS_SECRET_ACCESS_KEY environment
    variables"""

    config = json.load(file(conf_file))

    config["security_options"] = get_env()
    return config
