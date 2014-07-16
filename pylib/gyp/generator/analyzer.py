# Copyright (c) 2014 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This script is intended for use as a GYP_GENERATOR. It takes as input (by way of
the generator flag file_path) the list of relative file paths to consider. If
any target has at least one of the paths as a source (or input to an action or
rule) then 'Found dependency' is output, otherwise 'No dependencies' is output.
"""

import gyp.common
import gyp.ninja_syntax as ninja_syntax
import os
import posixpath

debug = False

generator_supports_multiple_toolsets = True

generator_wants_static_library_dependencies_adjusted = False

generator_default_variables = {
}
for dirname in ['INTERMEDIATE_DIR', 'SHARED_INTERMEDIATE_DIR', 'PRODUCT_DIR',
                'LIB_DIR', 'SHARED_LIB_DIR']:
  generator_default_variables[dirname] = '!!!'

for unused in ['RULE_INPUT_PATH', 'RULE_INPUT_ROOT', 'RULE_INPUT_NAME',
               'RULE_INPUT_DIRNAME', 'RULE_INPUT_EXT',
               'EXECUTABLE_PREFIX', 'EXECUTABLE_SUFFIX',
               'STATIC_LIB_PREFIX', 'STATIC_LIB_SUFFIX',
               'SHARED_LIB_PREFIX', 'SHARED_LIB_SUFFIX',
               'CONFIGURATION_NAME']:
  generator_default_variables[unused] = ''

def __ExtractBasePath(target):
  """Extracts the path components of the specified gyp target path."""
  last_index = target.rfind('/')
  if last_index == -1:
    return ''
  return target[0:(last_index + 1)]

def __ResolveParent(path, base_path_components):
  """Resolves |path|, which starts with at least one '../'. Returns an empty
  string if the path shouldn't be considered. See __AddSources() for a
  description of |base_path_components|."""
  depth = 0
  while path.startswith('../'):
    depth += 1
    path = path[3:]
  # Relative includes may go outside the source tree. For example, an action may
  # have inputs in /usr/include, which are not in the source tree.
  if depth > len(base_path_components):
    return ''
  if depth == len(base_path_components):
    return path
  return '/'.join(base_path_components[0:len(base_path_components) - depth]) + \
      '/' + path

def __AddSources(sources, base_path, base_path_components, result):
  """Extracts valid sources from |sources| and adds them to |result|. Each
  source file is relative to |base_path|, but may contain '..'. To make
  resolving '..' easier |base_path_components| contains each of the
  directories in |base_path|. Additionally each source may contain variables.
  Such sources are ignored as it is assumed dependencies on them are expressed
  and tracked in some other means."""
  # NOTE: gyp paths are always posix style.
  for source in sources:
    if not len(source) or source.startswith('!!!') or source.startswith('$'):
      continue
    # variable expansion may lead to //.
    org_source = source
    source = source[0] + source[1:].replace('//', '/')
    if source.startswith('../'):
      source = __ResolveParent(source, base_path_components)
      if len(source):
        result.append(source)
      continue
    result.append(base_path + source)
    if debug:
      print 'AddSource', org_source, result[len(result) - 1]

def __ExtractSourcesFromAction(action, base_path, base_path_components,
                               results):
  if 'inputs' in action:
    __AddSources(action['inputs'], base_path, base_path_components, results)

def __ExtractSources(target, target_dict, toplevel_dir):
  # |target| is either absolute or relative and in the format of the OS. Gyp
  # source paths are always posix. Convert |target| to a posix path relative to
  # |toplevel_dir_|. This is done to make it easy to build source paths.
  if os.sep == '\\' and os.altsep == '/':
    base_path = target.replace('\\', '/')
  else:
    base_path = target
  if base_path == toplevel_dir:
    base_path = ''
  elif base_path.startswith(toplevel_dir + '/'):
    base_path = base_path[len(toplevel_dir) + len('/'):]
  base_path = posixpath.dirname(base_path)
  base_path_components = base_path.split('/')

  # Add a trailing '/' so that __AddSources() can easily build paths.
  if len(base_path):
    base_path += '/'

  if debug:
    print 'ExtractSources', target, base_path

  results = []
  if 'sources' in target_dict:
    __AddSources(target_dict['sources'], base_path, base_path_components,
                 results)
  # Include the inputs from any actions. Any changes to these effect the
  # resulting output.
  if 'actions' in target_dict:
    for action in target_dict['actions']:
      __ExtractSourcesFromAction(action, base_path, base_path_components,
                                 results)
  if 'rules' in target_dict:
    for rule in target_dict['rules']:
      __ExtractSourcesFromAction(rule, base_path, base_path_components, results)

  return results

class Target(object):
  """Holds information about a particular target:
  sources: set of source files defined by this target. This includes inputs to
           actions and rules.
  deps: list of direct dependencies."""
  def __init__(self):
    self.sources = []
    self.deps = []

def __GenerateTargets(target_list, target_dicts, toplevel_dir):
  """Generates a dictionary with the key the name of a target and the value a
  Target. |toplevel_dir| is the root of the source tree."""
  targets = {}

  # Queue of targets to visit.
  targets_to_visit = target_list[:]

  while len(targets_to_visit) > 0:
    target_name = targets_to_visit.pop()
    if target_name in targets:
      continue

    target = Target()
    targets[target_name] = target
    target.sources.extend(__ExtractSources(target_name,
                                           target_dicts[target_name],
                                           toplevel_dir))

    for dep in target_dicts[target_name].get('dependencies', []):
      targets[target_name].deps.append(dep)
      targets_to_visit.append(dep)

  return targets

def __GetFiles(params):
  """Returns the list of files to analyze, or None if none specified."""
  generator_flags = params.get('generator_flags', {})
  file_path = generator_flags.get('file_path', None)
  if not file_path:
    return None
  try:
    f = open(file_path, 'r')
    result = []
    for file_name in f:
      if file_name.endswith('\n'):
        file_name = file_name[0:len(file_name) - 1]
      if len(file_name):
        result.append(file_name)
    f.close()
    return result
  except IOError:
    print 'Unable to open file', file_path
  return None

def CalculateVariables(default_variables, params):
  """Calculate additional variables for use in the build (called by gyp)."""
  flavor = gyp.common.GetFlavor(params)
  if flavor == 'mac':
    default_variables.setdefault('OS', 'mac')
  elif flavor == 'win':
    default_variables.setdefault('OS', 'win')
    # Copy additional generator configuration data from VS, which is shared
    # by the Windows Ninja generator.
    import gyp.generator.msvs as msvs_generator
    generator_additional_non_configuration_keys = getattr(msvs_generator,
        'generator_additional_non_configuration_keys', [])
    generator_additional_path_sections = getattr(msvs_generator,
        'generator_additional_path_sections', [])

    gyp.msvs_emulation.CalculateCommonVariables(default_variables, params)
  else:
    operating_system = flavor
    if flavor == 'android':
      operating_system = 'linux'  # Keep this legacy behavior for now.
    default_variables.setdefault('OS', operating_system)

def GenerateOutput(target_list, target_dicts, data, params):
  """Called by gyp as the final stage. Outputs results."""
  files = __GetFiles(params)
  if not files:
    print 'Must specify files to analyze via file_path generator flag'
    return

  toplevel_dir = os.path.abspath(params['options'].toplevel_dir)
  if os.sep == '\\' and os.altsep == '/':
    toplevel_dir = toplevel_dir.replace('\\', '/')
  if debug:
    print 'toplevel_dir', toplevel_dir
  targets = __GenerateTargets(target_list, target_dicts, toplevel_dir)

  files_set = frozenset(files)
  found_in_all_sources = 0
  for target_name, target in targets.iteritems():
    sources = files_set.intersection(target.sources)
    if len(sources):
      print 'Found dependency'
      if debug:
        print 'Found dependency in', target_name, target.sources
      return

  print 'No dependencies'
