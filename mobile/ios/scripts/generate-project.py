#!/usr/bin/env python3
"""Generate the small, dependency-free Xcode project deterministically."""
from pathlib import Path
from hashlib import sha256
import json
import subprocess

root = Path(__file__).resolve().parents[1]
objects = {}
# Retain signing and user-selected settings after Xcode edits the generated project.
project_file = root / "SodAI.xcodeproj/project.pbxproj"
previous = {}
if project_file.exists():
    previous = json.loads(subprocess.check_output(["plutil", "-convert", "json", "-o", "-", str(project_file)]))["objects"]

def uid(name):
    return sha256(name.encode()).hexdigest()[:24].upper()

def q(value):
    return json.dumps(str(value))

def add(name, content):
    key = uid(name)
    objects[key] = content
    return key

def refs(items):
    return "(" + ", ".join(items) + ",)"

def settings(values):
    return "{ " + " ".join(k + " = " + q(v) + ";" for k, v in values.items()) + " }"

targets = []
groups = []
products = []
for name, folder, kind in [
    ("SodAI", "SodAI", "application"),
    ("SodAITests", "SodAITests", "bundle.unit-test"),
    ("SodAIUITests", "SodAIUITests", "bundle.ui-testing"),
]:
    files, builds = [], []
    for path in sorted((root / folder).rglob("*.swift")):
        relative = str(path.relative_to(root))
        file_id = add("file:" + relative,
                      "{ isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = " + q(relative) + "; sourceTree = SOURCE_ROOT; }")
        files.append(file_id)
        builds.append(add("build:" + relative, "{ isa = PBXBuildFile; fileRef = " + file_id + "; }"))
    if name == "SodAI":
        files.append(add("info", '{ isa = PBXFileReference; lastKnownFileType = text.plist.xml; path = "SodAI/Info.plist"; sourceTree = SOURCE_ROOT; }'))
        files.append(add("entitlements", '{ isa = PBXFileReference; lastKnownFileType = text.plist.entitlements; path = "SodAI/SodAI.entitlements"; sourceTree = SOURCE_ROOT; }'))
    if name == "SodAI":
        files.append(uid("assets"))
    groups.append(add("group:" + name, "{ isa = PBXGroup; children = " + refs(files) + "; name = " + q(name) + '; sourceTree = "<group>"; }'))
    source = add("sources:" + name, "{ isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = " + refs(builds) + "; runOnlyForDeploymentPostprocessing = 0; }")
    frameworks = add("frameworks:" + name, "{ isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; }")
    resource_builds = []
    if name == "SodAI":
        asset = add("assets", '{ isa = PBXFileReference; lastKnownFileType = folder.assetcatalog; path = "SodAI/Assets.xcassets"; sourceTree = SOURCE_ROOT; }')
        resource_builds.append(add("build:assets", "{ isa = PBXBuildFile; fileRef = " + asset + "; }"))
    resources = add("resources:" + name, "{ isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = " + (refs(resource_builds) if resource_builds else "()") + "; runOnlyForDeploymentPostprocessing = 0; }")
    ext = ".app" if name == "SodAI" else ".xctest"
    product = add("product:" + name, "{ isa = PBXFileReference; explicitFileType = " + ("wrapper.application" if name == "SodAI" else "wrapper.cfbundle") + "; path = " + q(name + ext) + "; sourceTree = BUILT_PRODUCTS_DIR; }")
    products.append(product)
    configs = []
    for config in ["Debug", "Release"]:
        values = {
            "PRODUCT_NAME": "$(TARGET_NAME)", "PRODUCT_BUNDLE_IDENTIFIER": "me.sodai." + ("app" if name == "SodAI" else name),
            "IPHONEOS_DEPLOYMENT_TARGET": "26.0", "SWIFT_VERSION": "6.0", "TARGETED_DEVICE_FAMILY": "1",
            "GENERATE_INFOPLIST_FILE": "YES", "CODE_SIGN_STYLE": "Automatic",
            "SWIFT_OPTIMIZATION_LEVEL": "-Onone" if config == "Debug" else "-O",
            "SWIFT_ACTIVE_COMPILATION_CONDITIONS": "DEBUG" if config == "Debug" else "",
            "SUPPORTED_PLATFORMS": "iphoneos iphonesimulator",
            "ONLY_ACTIVE_ARCH": "YES" if config == "Debug" else "NO",
        }
        if name == "SodAI":
            values.update({"INFOPLIST_FILE": "SodAI/Info.plist", "MARKETING_VERSION": "0.1.0",
                           "CURRENT_PROJECT_VERSION": "1", "ENABLE_PREVIEWS": "YES",
                           "CODE_SIGN_ENTITLEMENTS": "SodAI/SodAI.entitlements"})
        elif name == "SodAITests":
            values.update({"TEST_HOST": "$(BUILT_PRODUCTS_DIR)/SodAI.app/SodAI", "BUNDLE_LOADER": "$(TEST_HOST)"})
        else:
            values["TEST_TARGET_NAME"] = "SodAI"
        for key, value in previous.get(uid(name + ":" + config), {}).get("buildSettings", {}).items():
            if key in {"DEVELOPMENT_TEAM", "CODE_SIGN_IDENTITY", "PROVISIONING_PROFILE_SPECIFIER", "PRODUCT_BUNDLE_IDENTIFIER", "MARKETING_VERSION", "CURRENT_PROJECT_VERSION"}:
                values[key] = value
        configs.append(add(name + ":" + config, "{ isa = XCBuildConfiguration; name = " + config + "; buildSettings = " + settings(values) + "; }"))
    config_list = add("configs:" + name, "{ isa = XCConfigurationList; buildConfigurations = " + refs(configs) + "; defaultConfigurationIsVisible = 0; defaultConfigurationName = Release; }")
    dependencies = []
    if name != "SodAI":
        proxy = add("proxy:" + name, "{ isa = PBXContainerItemProxy; containerPortal = " + uid("project") + "; proxyType = 1; remoteGlobalIDString = " + uid("target:SodAI") + "; remoteInfo = SodAI; }")
        dependencies.append(add("dependency:" + name, "{ isa = PBXTargetDependency; target = " + uid("target:SodAI") + "; targetProxy = " + proxy + "; }"))
    targets.append(add("target:" + name,
        "{ isa = PBXNativeTarget; buildConfigurationList = " + config_list +
        "; buildPhases = " + refs([source, frameworks, resources]) + "; buildRules = (); dependencies = " +
        (refs(dependencies) if dependencies else "()") + "; name = " + q(name) + "; productName = " + q(name) +
        "; productReference = " + product + '; productType = "com.apple.product-type.' + kind + '"; }'))

product_group = add("products", '{ isa = PBXGroup; children = ' + refs(products) + '; name = Products; sourceTree = "<group>"; }')
main_group = add("main", '{ isa = PBXGroup; children = ' + refs(groups + [product_group]) + '; sourceTree = "<group>"; }')
project_configs = []
for config in ["Debug", "Release"]:
    project_configs.append(add("project:" + config, "{ isa = XCBuildConfiguration; name = " + config + "; buildSettings = " + settings({
        "SDKROOT": "iphoneos", "CLANG_ENABLE_MODULES": "YES", "ENABLE_TESTABILITY": "YES" if config == "Debug" else "NO",
        "DEBUG_INFORMATION_FORMAT": "dwarf" if config == "Debug" else "dwarf-with-dsym",
    }) + "; }"))
project_config_list = add("project-configs", "{ isa = XCConfigurationList; buildConfigurations = " + refs(project_configs) + "; defaultConfigurationIsVisible = 0; defaultConfigurationName = Release; }")
add("project", "{ isa = PBXProject; attributes = { LastUpgradeCheck = 2700; }; buildConfigurationList = " +
    project_config_list + '; compatibilityVersion = "Xcode 14.0"; developmentRegion = ja; knownRegions = (ja, en, Base); mainGroup = ' +
    main_group + "; productRefGroup = " + product_group + '; projectDirPath = ""; projectRoot = ""; targets = ' + refs(targets) + "; }")
directory = root / "SodAI.xcodeproj"
directory.mkdir(exist_ok=True)
(directory / "project.pbxproj").write_text("// !$*UTF8*$!\n{ archiveVersion = 1; classes = {}; objectVersion = 56; objects = {\n" +
    "\n".join(k + " = " + v + ";" for k, v in objects.items()) + "\n}; rootObject = " + uid("project") + "; }\n")

def reference(name):
    return '<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="' + uid("target:" + name) + '" BuildableName="' + name + ('.app' if name == "SodAI" else '.xctest') + '" BlueprintName="' + name + '" ReferencedContainer="container:SodAI.xcodeproj"/>'

scheme = directory / "xcshareddata/xcschemes"
scheme.mkdir(parents=True, exist_ok=True)
if not (scheme / "SodAI.xcscheme").exists():
    (scheme / "SodAI.xcscheme").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<Scheme LastUpgradeVersion="2700" version="1.3"><BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries><BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES">' + reference("SodAI") +
    '</BuildActionEntry></BuildActionEntries></BuildAction><TestAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" shouldUseLaunchSchemeArgsEnv="YES"><Testables>' +
    "".join('<TestableReference skipped="NO">' + reference(n) + '</TestableReference>' for n in ["SodAITests", "SodAIUITests"]) +
    '</Testables></TestAction><LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" debugServiceExtension="internal" allowLocationSimulation="YES"><BuildableProductRunnable runnableDebuggingMode="0">' +
    reference("SodAI") + '</BuildableProductRunnable></LaunchAction><ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" savedToolIdentifier="" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"><BuildableProductRunnable runnableDebuggingMode="0">' +
    reference("SodAI") + '</BuildableProductRunnable></ProfileAction><AnalyzeAction buildConfiguration="Debug"/><ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/></Scheme>\n')
print(directory)
