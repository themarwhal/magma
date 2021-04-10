"""
Copyright 2021 The Magma Authors.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree.

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import os
import sys
import json

import click
from boto3 import Session

from .common import (
    run_command,
    run_playbook,
    print_error_msg,
    print_success_msg)


def setup_aws_creds():
    session = Session()
    creds = session.get_credentials()
    if not creds:
        print_error_msg('''
AWS credentials not configured.
configure through awscli or through orcl
orcl configure set -k aws_access_key_id -v <access_key_id>
orcl configure set -k aws_secret_access_key -v <aws_secret_access_key>
orcl configure set -k region -v <region>
''')
        sys.exit(1)

    frozen_creds = creds.get_frozen_credentials()
    os.environ["AWS_ACCESS_KEY_ID"] = frozen_creds.access_key
    os.environ["AWS_SECRET_ACCESS_KEY"] = frozen_creds.secret_key


@click.group(invoke_without_command=True)
@click.pass_context
def cleanup(ctx):
    """
    Removes resources deployed for orc8r
    """
    tf_destroy = ["terraform", "destroy", "-auto-approve"]

    if ctx.invoked_subcommand is None:
        cmd = " ".join(tf_destroy)
        click.echo(f"Following commands will be run during cleanup\n{cmd}")
        click.confirm('Do you want to continue with cleanup?', abort=True)
        click.echo(f"Running {cmd}")
        rc = run_command(tf_destroy)
        if rc != 0:
            print_error_msg(
                "Destroy Failed!!! Attempt cleaning up individual resources using 'orcl cleanup raw' subcommand")
            return


@cleanup.command()
@click.pass_context
@click.option('--dryrun', default=False, is_flag=True,
              help='Show resources to be cleaned up during raw cleanup')
@click.option('--state', help='Provide state file containing resource information e.g. terraform.tfstate or terraform.tfstate.backup')
@click.option('--values', multiple=True,
              help='Key value pairs. for e.g. cluster_name,orc8r. Can be used multiple times')
def raw(ctx, dryrun, state, values):
    """
    Individually cleans up resources deployed for orc8r
    """
    if state:
        ctx.obj['cleanup_state'] = state

    # add additional items
    for config_items in values:
        k, v = config_items.split(",")
        ctx.obj[k] = v

    extra_vars = json.dumps(ctx.obj)
    cleanup_playbook = "%s/cleanup.yml" % ctx.obj["playbooks"]
    playbook_args = ["ansible-playbook", "-v", "-e", extra_vars]

    # Few boto dependent modules in ansible require these values to be
    # setup as environment variables. Hence setting these up.
    setup_aws_creds()

    if dryrun:
        tag_args = ["-t", "cleanup_dryrun"]
    else:
        tag_args = ["-t", "cleanup"]

    rc = run_playbook(playbook_args + tag_args + [cleanup_playbook])
    if rc != 0:
        print_error_msg("Failed cleaning up resources!!!")
        sys.exit(1)
    print_success_msg("Successfully cleaned up underlying resources")
