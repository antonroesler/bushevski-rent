import sys
import os
import json
from aws_lambda_powertools import Logger

logger = Logger()


def handler(event, context):
    """Test handler to debug Python environment"""
    debug_info = {
        "message": "Debug info",
        "python_path": sys.path,
        "current_dir": os.getcwd(),
        "dir_contents": os.listdir("."),
        "parent_dir": os.path.exists(".."),
        "parent_dir_contents": os.listdir("..")
        if os.path.exists("..")
        else "No parent dir",
    }

    # Log the debug info
    print(debug_info)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(debug_info),
    }
