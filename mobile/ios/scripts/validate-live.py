#!/usr/bin/env python3
"""Opt-in device test against production. Creates one AI conversation, then archives it."""
import argparse
from pathlib import Path
import subprocess
import uuid
import xml.etree.ElementTree as XML

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--device', required=True)
parser.add_argument('--team', required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
schemes = root / 'SodAI.xcodeproj/xcshareddata/xcschemes'
name = 'SodAI-Live-' + uuid.uuid4().hex[:8]
path = schemes / (name + '.xcscheme')
tree = XML.parse(schemes / 'SodAI.xcscheme')
action = tree.find('TestAction')
action.set('shouldUseLaunchSchemeArgsEnv', 'NO')
variables = action.find('EnvironmentVariables')
if variables is None:
    variables = XML.SubElement(action, 'EnvironmentVariables')
XML.SubElement(variables, 'EnvironmentVariable', key='SODAI_LIVE_INTEGRATION', value='1', isEnabled='YES')
try:
    tree.write(path, encoding='UTF-8', xml_declaration=True)
    result = subprocess.run([
        'xcodebuild', '-project', str(root / 'SodAI.xcodeproj'), '-scheme', name,
        '-destination', 'platform=iOS,id=' + args.device,
        '-derivedDataPath', str(root / '.build-device'),
        '-resultBundlePath', str(root / '.build-device' / (name + '.xcresult')),
        '-only-testing:SodAITests', '-only-testing:SodAIUITests/SodAIUITests/testProductionScreensReadOnly',
        '-parallel-testing-enabled', 'NO', '-collect-test-diagnostics', 'never',
        '-allowProvisioningUpdates', 'DEVELOPMENT_TEAM=' + args.team, 'test'
    ])
finally:
    path.unlink(missing_ok=True)
raise SystemExit(result.returncode)
