// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "PersonalWorkflowApp",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(
            name: "PersonalWorkflowApp",
            targets: ["PersonalWorkflowApp"]
        )
    ],
    targets: [
        .executableTarget(
            name: "PersonalWorkflowApp"
        )
    ]
)
