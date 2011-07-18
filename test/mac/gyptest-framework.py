#!/usr/bin/env python

# Copyright (c) 2011 Google Inc. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Verifies that app bundles are built correctly.
"""

import TestGyp

import sys

if sys.platform == 'darwin':
  test = TestGyp.TestGyp(formats=['make', 'xcode'])

  test.run_gyp('framework.gyp', chdir='framework')

  test.build('framework.gyp', test.ALL, chdir='framework')

  # Binary
  test.built_file_must_exist('TestFramework.framework/Versions/A/TestFramework',
                             chdir='framework')

  # Info.plist
  test.built_file_must_exist(
      'TestFramework.framework/Versions/A/Resources/Info.plist',
      chdir='framework')

  # Resources
  test.built_file_must_exist(
      'TestFramework.framework/Versions/A/Resources/English.lproj/'
      'InfoPlist.strings',
      chdir='framework')

  # Symlinks created by packaging process
  test.built_file_must_exist('TestFramework.framework/Versions/Current',
                             chdir='framework')
  test.built_file_must_exist('TestFramework.framework/Resources',
                             chdir='framework')
  test.built_file_must_exist('TestFramework.framework/TestFramework',
                             chdir='framework')

  test.pass_test()

