// swift-tools-version: 6.0
import PackageDescription

// A lightweight macOS harness for the same production API/state code.
// The iPhone app and device UI tests remain in SodAI.xcodeproj.
let package = Package(
    name: "SodAICoreTests",
    platforms: [.macOS(.v15)],
    targets: [
        .target(
            name: "SodAI", path: "SodAI",
            exclude: [
                "App", "Assets.xcassets", "DesignSystem", "Development", "Features/Account",
                "Features/Chat", "Features/Threads", "Features/Brain/BrainView.swift",
                "Features/Brain/BrainBackground.swift", "Features/Brain/BrainConditionsView.swift",
                "Core/Models/PlatformStore.swift", "Info.plist", "SodAI.entitlements",
            ], sources: ["Core", "Features/Brain/BrainStore.swift"]),
        .testTarget(
            name: "SodAITests", dependencies: ["SodAI"], path: "SodAITests",
            exclude: ["AuthenticationTests.swift", "LivePlatformTests.swift"],
            sources: ["PlatformTests.swift", "PlatformTransportTests.swift"]),
    ]
)
