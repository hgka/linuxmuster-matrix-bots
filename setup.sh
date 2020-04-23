#!/bin/bash

python3 -m venv matrix-nio-env
source matrix-nio-env/bin/activate
pip3 install wheel
pip3 install matrix-nio requests
