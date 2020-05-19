# form Kimberly's code
import json
import os
import argparse
import sys
import logging
from tx.fhir.utils import bundle, unbundle

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

def get_patient_resource_entry_array(json_in_dir, pid, resource_name):
    resource_path=os.path.join(os.path.join(json_in_dir, resource_name))
    rescs_filtered = []
    if os.path.isdir(resource_path):
        for f in os.listdir(resource_path):
            pid_fn=os.path.join(resource_path, f)
            with open(pid_fn, encoding='latin-1') as pid_fp:
                rescs = unbundle(json.load(pid_fp)).value
                print("rescs =", rescs)
                if resource_name == "Patient":
                    rescs_filtered.extend(filter(lambda x: x["id"] == pid, rescs))
                else:
                    rescs_filtered.extend(filter(lambda x: x["subject"]["reference"] == f"Patient/{pid}", rescs))
    
        return bundle(rescs_filtered)


def get_entries(json_in_dir, pid, resource_names):
    entries = {}
    for resource in resource_names:
        entries[resource] = get_patient_resource_entry_array(json_in_dir, pid, resource)
    return entries

