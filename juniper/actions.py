# -*- coding: utf-8 -*-
"""
    actions.py
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
import shutil
import subprocess
from jinja2 import Template
import functools

from juniper.constants import DEFAULT_OUT_DIR, DEFAULT_DOCKER_IMAGE
from juniper.io import (get_artifact, write_tmp_file, get_artifact_path)


def build_artifacts(logger, manifest):
    """
    Creates a .zip file for each one of the serverless functions defined in the given
    manifest definitions file. Each function must include a name, and the set of directories
    to be included in the artifact. As part of the packaging, if the given function
    has a definition of a requirements file, all the dependencies in that file will be
    included in the artifact.

    :param logger: The logger instance.
    :param manifest: The definition of the functions and global parameters as defined in the input file.
    """

    compose_fn = build_compose(logger, manifest)
    logger.debug(f'docker compose -f {compose_fn} --project-directory . run sample-lambda bash')
    try:
        # Must copy the bin directory to the client's folder structure. This directory
        # will be promtly cleaned up after the artifacts are built.
        os.makedirs('./.juni/bin', exist_ok=True)
        with get_artifact_path('package.sh') as path:
            shutil.copy(path, './.juni/bin/')
        with get_artifact_path('build_layer.sh') as path:
            shutil.copy(path, './.juni/bin/')

        # Use docker as a way to pip install dependencies, and copy the business logic
        # specified in the function definitions.
        subprocess.run(["docker", "compose", "-f", compose_fn, '--project-directory', '.', 'down', '--remove-orphans'])
        subprocess.run(["docker", "compose", "-f", compose_fn, '--project-directory', '.', 'up'])
        subprocess.run(["docker", "compose", "-f", compose_fn, '--project-directory', '.', 'down'])
    finally:
        shutil.rmtree('./.juni', ignore_errors=True)


def build_compose(logger, manifest):
    """
    Builds a docker compose file with the lambda functions defined in the manifest.
    The definition of the lambda functions includes the name of the function as
    well as the set of dependencies to include in the packaging.

    :param logger: The logger instance.
    :param manifest: The yaml file that contains the info of the functions to package.
    """

    compose = _get_compose_template(manifest)
    # Returns the name of the temp file that has the docker compose definition.
    return write_tmp_file(compose)


def _get_compose_template(manifest):
    """
    Build the service entry for each one of the functions in the given context.
    Each docker compose entry will depend on the same image and it's just a static
    definition that gets built from a template. The template is in the artifacts
    folder.
    """
    artifact = get_artifact('compose-template.yml')

    def build_section(label):
        return [
            {
                'name': name,
                'image': _get_docker_image(manifest, sls_section),
                'platform': _get_platform(manifest, sls_section),
                'volumes': _get_volumes(manifest, sls_section)
            }
            for name, sls_section in manifest.get(label, {}).items()
        ]

    # Load the jinja template and build the sls functions and layers.
    return Template(artifact).render(
        functions=build_section('functions'),
        layers=build_section('layers')
    )


def _get_volumes(manifest, sls_function):
    """
    Get the docker compose volume mapping from the includes block of a serverless
    function definition. Each entry will be mapped to its own entry in the docker
    container.

    :param manifest: The entire juniper manifest.
    :param sls_function: The serverless function definition.
    """

    def get_vol(include):

        if include == './':
            return './:/var/task/common/'

        norm_include = include.rstrip('/')
        name = norm_include[norm_include.rindex('/') + 1:]
        return f'{norm_include}:/var/task/common/{name}'

    output_dir = manifest.get('output_dir', DEFAULT_OUT_DIR)
    volumes = [
        f'{output_dir}:/var/task/dist',
        './.juni/bin:/var/task/bin',
    ] + [
        get_vol(include)
        for include in sls_function.get('include', [])
    ]

    reqs_path = sls_function.get('requirements')
    if reqs_path:
        volumes.append(f'{reqs_path}:/var/task/common/requirements.txt')

    conf_path = manifest.get('global', {}).get('pipconf')
    if conf_path:
        volumes.append(f'{conf_path}:/etc/pip.conf')

    return volumes


def _get_attr(key, default, manifest, sls_function):
    """
    Get an attribute from the manifest, looking under the function first,
    then global:, and finally using a default.


    :params key: The key to retrieve
    :params default: The value to return if your key is not defined anywhere
    :params manifest: The juniper manifest file.
    :params sls_function: The serverless function definition.
    """
    function_value = sls_function.get(key)
    if function_value:
        return function_value

    global_value = manifest.get('global', {}).get(key)
    if global_value:
        return global_value

    return default


_get_docker_image = functools.partial(_get_attr, "image", DEFAULT_DOCKER_IMAGE)
_get_platform = functools.partial(_get_attr, "platform", None)
