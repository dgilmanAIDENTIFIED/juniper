# -*- coding: utf-8 -*-
"""
    io.py
    :copyright: © 2019 by the EAB Tech team.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
        http://www.apache.org/licenses/LICENSE-2.0
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""


import os
import yaml
import tempfile
import importlib.resources
import contextlib
import pathlib


def reader(file_name):

    with open(file_name, 'r') as stream:
        return yaml.safe_load(stream)


def write_tmp_file(content):

    new_file, file_name = tempfile.mkstemp()

    os.write(new_file, content.encode())
    os.close(new_file)
    return file_name


def get_artifact(template_name):

    fn_template_path = get_artifact_path(template_name)
    with fn_template_path as path:
        with path.open("r") as fd:
            return fd.read()


def get_artifact_path(artifact_name) -> contextlib.AbstractContextManager[pathlib.Path]:
    """
    Reads an artifact out of the rio-tools project.
    """
    files = importlib.resources.files("juniper")
    return importlib.resources.as_file(files.joinpath(os.path.join('artifacts', artifact_name)))
