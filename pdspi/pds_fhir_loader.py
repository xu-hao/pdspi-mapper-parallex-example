# form Kimberly's code
import json
import os
import argparse
import sys
import logging
from tx.fhir.utils import bundle, unbundle
from typing import List

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

def get_patient_resource_entry_array(json_in_dir, pid : str, resource_name):
    resource_path=os.path.join(os.path.join(json_in_dir, resource_name))
    rescs_filtered = []
    if os.path.isdir(resource_path):
        for root, _, files in os.walk(resource_path):
            for f in files:
                pid_fn=os.path.join(root, f)
                logger.info(f"looking into {pid_fn}")
                with open(pid_fn, encoding='latin-1') as pid_fp:
                    rescs = unbundle(json.load(pid_fp)).value
                    logger.info(f"rescs = {rescs}")
                    if resource_name == "Patient":
                        rescs_filtered.extend(filter(lambda x: x["id"] == pid, rescs))
                    else:
                        patient_reference = f"Patient/{pid}"
                        rescs_filtered.extend(filter(lambda x: x["subject"]["reference"] == patient_reference, rescs))
    
    return bundle(rescs_filtered)


def get_entries(json_in_dir, pids : List[str], resource_names):
    patient_entries = {}
    for pid in pids:
        entries = {}
        for resource in resource_names:
            entries[resource] = get_patient_resource_entry_array(json_in_dir, pid, resource)
        patient_entries[pid] = entries
    return patient_entries

