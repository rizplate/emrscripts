#!/usr/bin/env python

import boto
import boto
import boto.emr
from boto.s3.key import Key
from boto.emr.bootstrap_action import BootstrapAction
from boto.emr.instance_group import InstanceGroup
from boto.emr.step import ScriptRunnerStep
import time
import os
import sys

# usage: emr.py -i <pig-script>

# upload script to s3
# clean existing results from s3, if any
# use jarno-interactive cluster, if exists
# launch script
# monitor progress
# set up ssh tunnel to job tracker
# sync results back, concatenate to single file

confpath = os.path.join(os.path.dirname(__file__), 'emr.conf.py')
conf = exec(open(confpath).read())

try:
    script_name = sys.argv[1]
except:
    sys.stderr.write('Usage: emr.py <pig-script>\n')
    sys.exit(1)

# upload script to s3
s3_conn = boto.connect_s3()
k = Key(s3_conn.get_bucket(bucket_name))
k.key = 'emrunner/' + script_name
k.set_contents_from_file(open(script_name))
script_uri = 's3://%s/emrunner/%s' % (bucket_name, script_name)
s3_conn.close()

emr_conn = boto.emr.connect_to_region('us-east-1')

instance_groups = [
    InstanceGroup(1, 'MASTER', 'm2.4xlarge', 'ON_DEMAND', 'MASTER_GROUP'),
    InstanceGroup(3, 'CORE', 'm2.4xlarge', 'ON_DEMAND', 'CORE_GROUP'),
]

bootstrap_actions = [
    BootstrapAction('install-pig', install_pig_script, [pig_version]),
]

steps = [
    ScriptRunnerStep(script_name, step_args=['/home/hadoop/pig/bin/pig', '-f', script_uri, '-l', '.'])
]

# use jarno-interactive cluster, if exists
jobids = [c.id for c in emr_conn.list_clusters(cluster_states=['WAITING']).clusters
          if c.name == default_cluster_name]

if not jobids:
    jobid = emr_conn.run_jobflow(
        name=os.environ['USER'] + '-' + script_name,
        keep_alive=False,
        ami_version=ami_version,
        visible_to_all_users=True,
        ec2_keyname=ec2_keyname,
        log_uri=log_uri,
        action_on_failure='TERMINATE',
        instance_groups=instance_groups,
        bootstrap_actions=bootstrap_actions)
else:
    jobid = jobids[0]
print(jobid)

emr_conn.add_jobflow_steps(jobid, steps)

status = 'asdf'
while status != 'TERMINATED' and status != 'WAITING':
    status = emr_conn.describe_jobflow(jobid).state
    sys.stdout.write('\r%s          ' % status)
    sys.stdout.flush()
    time.sleep(5)

sys.stdout.write('\n')

emr_conn.close()