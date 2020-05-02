# form Kimberly's code
import json
import os
import argparse
import sys
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

def pid_json_fullpath(pid_file_name, resource_path):
    for root, dirs, files in os.walk(resource_path):
        if pid_file_name in files:
            return os.path.join(root, pid_file_name)


def get_patient_resource_entry_array(json_in_dir, pid, resource_name):
    resource_path=os.path.join(os.path.join(json_in_dir, resource_name))
    pid_fn=pid_json_fullpath(pid+".json", resource_path)
    logger.debug("+D pid_fn:"+str(pid_fn)+",pid="+pid+", path="+resource_path+"\n")
    if pid_fn is None :
        logger.debug("+ ["+pid+"] ERROR no ["+resource_path+"] found\n")
        return False
    with open(pid_fn, encoding='latin-1') as pid_fp:
        return json.load(pid_fp)


def get_entries(json_in_dir, pid, resource_names):
    if len(resource_names) == 1:
        return get_patient_resource_entry_array(json_in_dir, pid, resource_names[0])
    else:
        entries = {}
        for resource in resource_names:
            entries[resource] = get_patient_resource_entry_array(json_in_dir, pid, resource)
        return entries

